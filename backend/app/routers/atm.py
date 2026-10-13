"""Customer Face ATM terminal, biometric authentication, and simulated transactions router."""

import re
import base64
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.responses import HTMLResponse
from google.cloud import firestore as gcloud_firestore

from app.core.config import settings
from app.core.firebase import get_firestore_client
from app.core.security import get_current_customer
from app.core.crypto import validate_luhn_card_number, mask_card_number
from app.services.face_service import face_service, FaceProcessingError
from app.services.email_service import email_service
from app.services.incident_storage import incident_storage, validate_image_bytes
from app.schemas.atm import (
    CardValidateRequest,
    CardValidateResponse,
    FaceLoginRequest,
    CustomerSessionResponse,
    SimulatedTransactionRequest,
    SimulatedTransactionResponse,
    BalanceResponse,
    CustomerDashboardResponse,
    FaceCheckRequest,
    FaceCheckResponse,
    OwnerAlertDecisionRequest,
    OwnerIncidentDetailsResponse,
)

logger = logging.getLogger("face_atm.atm")
router = APIRouter(prefix="/api/atm", tags=["ATM Terminal"])


@router.post("/card-validate", response_model=CardValidateResponse)
async def validate_atm_card(payload: CardValidateRequest):
    """
    Validate customer Face ATM card number and check account status and lockouts.
    Does not expose sensitive credentials, embeddings, or full account data.
    """
    clean_card = re.sub(r"[\s-]", "", payload.cardNumber)

    # 1. Luhn checksum algorithm check
    if not validate_luhn_card_number(clean_card):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid card number checksum. Please check the digits entered.",
        )

    db = get_firestore_client()
    card_ref = db.collection("cards").document(clean_card)
    card_doc = card_ref.get()

    if not card_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found. Please enter a valid registered Face ATM card number.",
        )

    card_data = card_doc.to_dict()
    if card_data.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This card is inactive or has been deactivated. Please contact administration.",
        )

    customer_id = card_data.get("customerId")
    cust_ref = db.collection("customers").document(customer_id)
    cust_doc = cust_ref.get()

    if not cust_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer account record associated with this card was not found.",
        )

    cust_data = cust_doc.to_dict()

    if cust_data.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is currently suspended. Please contact bank administration.",
        )

    if not cust_data.get("faceEnrolled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biometric enrollment is pending for this card. Please complete enrollment first.",
        )

    # 2. Check temporary lockout status
    now = datetime.now(timezone.utc)
    locked_until_str = cust_data.get("lockedUntil")
    is_locked = False
    remaining_seconds = None

    if locked_until_str:
        try:
            locked_until = datetime.fromisoformat(locked_until_str)
            if now < locked_until:
                is_locked = True
                remaining_seconds = int((locked_until - now).total_seconds())
            else:
                # Lockout expired: reset lockout on customer record
                cust_ref.update({"lockedUntil": None, "failedAttempts": 0})
        except Exception:
            pass

    card_masked = mask_card_number(clean_card)
    full_name = cust_data.get("fullName", "Customer")

    if is_locked:
        return CardValidateResponse(
            valid=False,
            cardNumberMasked=card_masked,
            fullName=full_name,
            isLocked=True,
            lockoutRemainingSeconds=remaining_seconds,
            message=f"Card is temporarily locked for security. Please try again in {int(remaining_seconds // 60) + 1} minute(s).",
        )

    return CardValidateResponse(
        valid=True,
        cardNumberMasked=card_masked,
        fullName=full_name,
        isLocked=False,
        lockoutRemainingSeconds=None,
        message="Card validated. Please face the camera directly to verify your identity.",
    )


@router.post("/face-check", response_model=FaceCheckResponse)
async def check_live_face_presence(payload: FaceCheckRequest):
    """
    Fast live camera frame presence check using existing YuNet face detector.
    Does not authenticate, does not extract embeddings, does not increment failed attempts.
    Returns recognizable=True if face is clearly visible, or recognizable=False if face is hidden/obscured/turned away.
    """
    raw_b64 = payload.imageBase64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
        validate_image_bytes(image_bytes)
    except Exception:
        return FaceCheckResponse(
            recognizable=False,
            confidence=None,
            message="Face Not Recognizable — Please show your full face to the camera.",
        )

    res = face_service.detect_face_presence(image_bytes)
    return FaceCheckResponse(
        recognizable=res.get("recognizable", False),
        confidence=res.get("confidence"),
        message=res.get("message", "Face Not Recognizable — Please show your full face to the camera."),
    )


@router.post("/login-face", response_model=CustomerSessionResponse)
async def authenticate_face_login(payload: FaceLoginRequest):
    """
    Biometric face verification and customer session issuance.
    Captures fresh live camera face, compares embedding with enrolled profile,
    enforces rate limits/lockouts, and raises security alerts upon failure.
    """
    clean_card = re.sub(r"[\s-]", "", payload.cardNumber)

    # 1. Luhn check
    if not validate_luhn_card_number(clean_card):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid card number checksum.",
        )

    db = get_firestore_client()
    card_ref = db.collection("cards").document(clean_card)
    card_doc = card_ref.get()

    if not card_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not recognized.",
        )

    customer_id = card_doc.to_dict().get("customerId")
    cust_ref = db.collection("customers").document(customer_id)
    cust_doc = cust_ref.get()

    if not cust_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer record not found.",
        )

    cust_data = cust_doc.to_dict()
    now = datetime.now(timezone.utc)

    # 2. Check existing lockout
    locked_until_str = cust_data.get("lockedUntil")
    if locked_until_str:
        try:
            locked_until = datetime.fromisoformat(locked_until_str)
            if now < locked_until:
                remaining_minutes = int((locked_until - now).total_seconds() // 60) + 1
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Card is locked due to multiple failed verification attempts. Please retry in {remaining_minutes} minute(s) or contact branch administration.",
                )
            else:
                cust_ref.update({"lockedUntil": None, "failedAttempts": 0})
                cust_data["failedAttempts"] = 0
        except HTTPException:
            raise
        except Exception:
            pass

    # 3. Retrieve enrolled biometric face embedding
    bio_doc = cust_ref.collection("biometrics").document("face").get()
    if not bio_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enrolled face biometric profile found for this customer. Please contact administration.",
        )

    enrolled_embedding = bio_doc.to_dict().get("embedding")
    if not enrolled_embedding or len(enrolled_embedding) != 128:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Enrolled biometric template is incomplete or corrupt. Please re-enroll face.",
        )

    # 4. Decode camera capture and validate payload
    raw_b64 = payload.imageBase64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
        validate_image_bytes(image_bytes)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid camera image payload: {exc}",
        )

    card_masked = mask_card_number(clean_card)
    full_name = cust_data.get("fullName", "Customer")
    recipient_email = cust_data.get("email")

    # 5. Pipeline Step 1 & 2: YuNet face detection & Anti-spoofing liveness check (Fail-closed)
    try:
        capture_result = face_service.verify_liveness_and_extract_embedding(
            image_bytes=image_bytes,
            consent_obtained=True,
            check_liveness=settings.FACE_ANTISPOOF_ENABLED,
            liveness_threshold=settings.FACE_ANTISPOOF_THRESHOLD if settings.FACE_ANTISPOOF_ENABLED else None,
        )
    except FaceProcessingError as exc:
        if exc.status_code == 403:
            # Presentation attack / spoof attempt rejected
            current_failed = cust_data.get("failedAttempts", 0) + 1
            max_attempts = settings.CUSTOMER_MAX_FAILED_ATTEMPTS
            is_now_locked = current_failed >= max_attempts

            updates: Dict[str, Any] = {"failedAttempts": current_failed}
            if is_now_locked:
                lockout_expiry = now + timedelta(minutes=settings.CUSTOMER_LOCKOUT_MINUTES)
                updates["lockedUntil"] = lockout_expiry.isoformat()

                # Trigger security approval workflow
                approval_id = f"sec_{secrets.token_hex(16)}"
                approval_expiry = now + timedelta(minutes=settings.CUSTOMER_LOCKOUT_MINUTES)

                # Securely store actual captured failed-attempt image
                incident_storage.save_incident_image(
                    approval_id=approval_id,
                    image_bytes=image_bytes,
                    db=db,
                )

                db.collection("security_approvals").document(approval_id).set({
                    "id": approval_id,
                    "customerId": customer_id,
                    "customerName": full_name,
                    "customerEmail": recipient_email,
                    "cardNumberMasked": card_masked,
                    "reason": f"Biometric presentation attack detected ({current_failed}/{max_attempts})",
                    "failedAttempts": current_failed,
                    "status": "PENDING",
                    "createdAt": now.isoformat(),
                    "expiresAt": approval_expiry.isoformat(),
                    "reviewedBy": None,
                    "reviewedAt": None,
                    "used": False,
                    "hasCapturedImage": True,
                    "notes": "Anti-spoofing PAD triggered; customer card temporarily locked.",
                })

                try:
                    await email_service.send_security_alert_email(
                        recipient_email=recipient_email,
                        recipient_name=full_name,
                        card_number_masked=card_masked,
                        attempt_timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        failed_attempts=current_failed,
                        is_locked=True,
                        lockout_minutes=settings.CUSTOMER_LOCKOUT_MINUTES,
                        lockout_expiry=approval_expiry.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        image_bytes=image_bytes,
                    )
                except Exception as mail_err:
                    logger.error("Security alert email delivery failed: %s", mail_err)

                cust_ref.update(updates)
                db.collection("audit_logs").add({
                    "action": "ATM_AUTH_SPOOF_LOCKOUT_TRIGGERED",
                    "customerId": customer_id,
                    "cardNumberMasked": card_masked,
                    "failedAttempts": current_failed,
                    "timestamp": now.isoformat(),
                    "status": "LOCKED",
                })
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Biometric presentation attack detected. Card is temporarily locked for {settings.CUSTOMER_LOCKOUT_MINUTES} minutes.",
                )
            else:
                cust_ref.update(updates)
                db.collection("audit_logs").add({
                    "action": "ATM_AUTH_SPOOF_REJECTED",
                    "customerId": customer_id,
                    "cardNumberMasked": card_masked,
                    "failedAttempts": current_failed,
                    "timestamp": now.isoformat(),
                    "status": "SPOOF_REJECTED",
                })
                remaining = max_attempts - current_failed
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{exc.message} ({remaining} attempt(s) remaining before security lockout).",
                )
        else:
            # Geometry, lighting, multi-face or model unavailable errors
            error_detail = exc.message
            if "face not recognizable" in exc.message.lower() or "no face detected" in exc.message.lower() or "confidence" in exc.message.lower() or "too small" in exc.message.lower():
                error_detail = "Face Not Recognizable — Please show your full face to the camera."
            raise HTTPException(status_code=exc.status_code, detail=error_detail)
    except Exception as exc:
        logger.error("Camera face extraction error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    captured_embedding = capture_result["embedding"]

    # 6. Pipeline Step 3: Biometric SFace comparison (Executed ONLY after liveness passes!)
    try:
        match_result = face_service.compare_embeddings(
            captured_embedding,
            enrolled_embedding,
            threshold=settings.FACE_MATCH_THRESHOLD,
        )
    except Exception as exc:
        logger.error("Embedding comparison failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Biometric comparison engine encountered an internal error.",
        )

    # 7. Handle Face Verification Failure
    if not match_result.get("matched"):
        current_failed = cust_data.get("failedAttempts", 0) + 1
        max_attempts = settings.CUSTOMER_MAX_FAILED_ATTEMPTS
        is_now_locked = current_failed >= max_attempts

        updates: Dict[str, Any] = {"failedAttempts": current_failed}

        if is_now_locked:
            lockout_expiry = now + timedelta(minutes=settings.CUSTOMER_LOCKOUT_MINUTES)
            updates["lockedUntil"] = lockout_expiry.isoformat()

            # Create security approval request for administrator / card owner review
            approval_id = f"sec_{secrets.token_hex(16)}"
            approval_expiry = now + timedelta(minutes=settings.CUSTOMER_LOCKOUT_MINUTES)

            # Securely store actual captured failed-attempt image
            incident_storage.save_incident_image(
                approval_id=approval_id,
                image_bytes=image_bytes,
                db=db,
            )

            # Generate short-lived signed HMAC decision tokens for the real card owner
            accept_token = incident_storage.generate_owner_decision_token(
                approval_id=approval_id,
                customer_id=customer_id,
                action="ACCEPT",
                expiry_seconds=settings.CUSTOMER_LOCKOUT_MINUTES * 60,
            )
            deny_token = incident_storage.generate_owner_decision_token(
                approval_id=approval_id,
                customer_id=customer_id,
                action="DENY",
                expiry_seconds=settings.CUSTOMER_LOCKOUT_MINUTES * 60,
            )

            db.collection("security_approvals").document(approval_id).set({
                "id": approval_id,
                "customerId": customer_id,
                "customerName": full_name,
                "customerEmail": recipient_email,
                "cardNumberMasked": card_masked,
                "reason": f"Maximum biometric verification failures reached ({current_failed}/{max_attempts})",
                "failedAttempts": current_failed,
                "status": "PENDING",
                "createdAt": now.isoformat(),
                "expiresAt": approval_expiry.isoformat(),
                "reviewedBy": None,
                "reviewedAt": None,
                "used": False,
                "hasCapturedImage": True,
                "notes": None,
                "source": "FACE_MISMATCH",
            })

            # Send Security Alert Email with attached failed-attempt image and ACCEPT / DENY options
            try:
                await email_service.send_security_alert_email(
                    recipient_email=recipient_email,
                    recipient_name=full_name,
                    card_number_masked=card_masked,
                    attempt_timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    failed_attempts=current_failed,
                    is_locked=True,
                    lockout_minutes=settings.CUSTOMER_LOCKOUT_MINUTES,
                    lockout_expiry=approval_expiry.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    image_bytes=image_bytes,
                    approval_id=approval_id,
                    accept_token=accept_token,
                    deny_token=deny_token,
                )
            except Exception as mail_err:
                logger.error("Security alert email delivery failed: %s", mail_err)

            cust_ref.update(updates)

            # Record security audit log
            db.collection("audit_logs").add({
                "action": "ATM_AUTH_LOCKOUT_TRIGGERED",
                "customerId": customer_id,
                "cardNumberMasked": card_masked,
                "failedAttempts": current_failed,
                "timestamp": now.isoformat(),
                "status": "LOCKED",
            })

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Face verification did not match. Card is temporarily locked for {settings.CUSTOMER_LOCKOUT_MINUTES} minutes.",
            )
        else:
            cust_ref.update(updates)

            # Record security audit log for below-lockout failed attempt
            db.collection("audit_logs").add({
                "action": "ATM_AUTH_FACE_MISMATCH",
                "customerId": customer_id,
                "cardNumberMasked": card_masked,
                "failedAttempts": current_failed,
                "timestamp": now.isoformat(),
                "status": "FAILED",
            })

            remaining = max_attempts - current_failed
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Face verification did not match enrolled profile. {remaining} attempt(s) remaining.",
            )

    # 8. Biometric Match Succeeded: Reset failed attempts & issue session
    cust_ref.update({
        "failedAttempts": 0,
        "lockedUntil": None,
        "lastSuccessfulLogin": now.isoformat(),
    })

    # Ensure simulated initial balance exists
    balance = cust_data.get("balance")
    if balance is None:
        balance = settings.DEFAULT_INITIAL_BALANCE
        cust_ref.update({"balance": balance})

    # Create server-validated short-lived customer session
    session_token = f"cust_sess_{secrets.token_hex(24)}"
    session_expiry = now + timedelta(minutes=settings.CUSTOMER_SESSION_EXPIRY_MINUTES)

    db.collection("customer_sessions").document(session_token).set({
        "sessionId": session_token,
        "customerId": customer_id,
        "fullName": full_name,
        "cardNumberMasked": card_masked,
        "email": recipient_email,
        "createdAt": now.isoformat(),
        "expiresAt": session_expiry.isoformat(),
        "active": True,
    })

    db.collection("audit_logs").add({
        "action": "ATM_AUTH_SUCCESS",
        "customerId": customer_id,
        "cardNumberMasked": card_masked,
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return CustomerSessionResponse(
        success=True,
        sessionToken=session_token,
        customerId=customer_id,
        fullName=full_name,
        cardNumberMasked=card_masked,
        balance=float(balance),
        expiresInMinutes=settings.CUSTOMER_SESSION_EXPIRY_MINUTES,
        message="Face verification successful. Welcome to Face ATM.",
    )


@router.get("/dashboard", response_model=CustomerDashboardResponse)
async def get_customer_dashboard(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """
    Retrieve authenticated customer's dashboard profile, balance, and recent transaction history.
    Strictly isolated: customer can only access their own record.
    """
    db = get_firestore_client()
    customer_id = current_customer["customerId"]

    cust_doc = db.collection("customers").document(customer_id).get()
    if not cust_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    cust_data = cust_doc.to_dict()
    balance = float(cust_data.get("balance", settings.DEFAULT_INITIAL_BALANCE))

    # Query recent 10 transactions
    recent_transactions = []
    try:
        txns_stream = (
            db.collection("customers")
            .document(customer_id)
            .collection("transactions")
            .order_by("timestamp", direction=gcloud_firestore.Query.DESCENDING)
            .limit(10)
            .stream()
        )
        for t_doc in txns_stream:
            t_data = t_doc.to_dict()
            recent_transactions.append({
                "id": t_doc.id,
                "type": t_data.get("type"),
                "amount": float(t_data.get("amount", 0.0)),
                "newBalance": float(t_data.get("newBalance", 0.0)),
                "timestamp": t_data.get("timestamp"),
                "status": t_data.get("status", "COMPLETED"),
                "description": t_data.get("description", "Simulated ATM Transaction"),
            })
    except Exception as exc:
        logger.warning("Failed to query transaction history: %s", exc)

    return CustomerDashboardResponse(
        customerId=customer_id,
        fullName=cust_data.get("fullName", current_customer.get("fullName")),
        cardNumberMasked=cust_data.get("cardNumberMasked", current_customer.get("cardNumberMasked")),
        balance=balance,
        currency="INR",
        bankName=cust_data.get("bankName", "Face ATM"),
        status=cust_data.get("status", "ACTIVE"),
        isSimulated=True,
        recentTransactions=recent_transactions,
    )


@router.get("/balance", response_model=BalanceResponse)
async def check_balance(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """Balance inquiry for authenticated customer."""
    db = get_firestore_client()
    customer_id = current_customer["customerId"]

    cust_doc = db.collection("customers").document(customer_id).get()
    if not cust_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    cust_data = cust_doc.to_dict()
    balance = float(cust_data.get("balance", settings.DEFAULT_INITIAL_BALANCE))
    now = datetime.now(timezone.utc)

    # Record inquiry audit log
    db.collection("audit_logs").add({
        "action": "ATM_BALANCE_INQUIRY",
        "customerId": customer_id,
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return BalanceResponse(
        customerId=customer_id,
        fullName=cust_data.get("fullName", current_customer.get("fullName")),
        cardNumberMasked=cust_data.get("cardNumberMasked", current_customer.get("cardNumberMasked")),
        balance=balance,
        currency="INR",
        isSimulated=True,
        asOf=now.isoformat(),
    )


@router.post("/withdraw", response_model=SimulatedTransactionResponse)
async def withdraw_cash_simulated(
    payload: SimulatedTransactionRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """
    Simulated ATM cash withdrawal with atomic Firestore transactional locking.
    Prevents double-spending, race conditions, and negative balances.
    """
    db = get_firestore_client()
    customer_id = current_customer["customerId"]
    cust_ref = db.collection("customers").document(customer_id)
    now = datetime.now(timezone.utc)

    # Atomic transactional balance verification and deduction
    @gcloud_firestore.transactional
    def execute_withdrawal(transaction, ref, withdraw_amount):
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="Customer record not found.")

        data = snapshot.to_dict()
        cur_balance = float(data.get("balance", settings.DEFAULT_INITIAL_BALANCE))

        if cur_balance < withdraw_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds. Current balance is ₹{cur_balance:,.2f}, requested withdrawal is ₹{withdraw_amount:,.2f}.",
            )

        updated_balance = round(cur_balance - withdraw_amount, 2)
        transaction.update(ref, {
            "balance": updated_balance,
            "lastTransactionAt": now.isoformat(),
        })
        return cur_balance, updated_balance

    try:
        cur_bal, new_bal = execute_withdrawal(db.transaction(), cust_ref, payload.amount)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Withdrawal transaction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction processing error. Please try again.",
        )

    # Record completed transaction record
    txn_id = f"txn_w_{secrets.token_hex(12)}"
    txn_record = {
        "id": txn_id,
        "customerId": customer_id,
        "type": "WITHDRAWAL",
        "amount": payload.amount,
        "previousBalance": cur_bal,
        "newBalance": new_bal,
        "currency": "INR",
        "isSimulated": True,
        "status": "COMPLETED",
        "description": "Simulated ATM Cash Withdrawal",
        "timestamp": now.isoformat(),
    }

    # Store in customer transactions subcollection and root transactions
    db.collection("customers").document(customer_id).collection("transactions").document(txn_id).set(txn_record)
    db.collection("transactions").document(txn_id).set(txn_record)

    db.collection("audit_logs").add({
        "action": "ATM_WITHDRAWAL_SUCCESS",
        "customerId": customer_id,
        "transactionId": txn_id,
        "amount": payload.amount,
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return SimulatedTransactionResponse(
        success=True,
        transactionId=txn_id,
        type="WITHDRAWAL",
        amount=payload.amount,
        previousBalance=cur_bal,
        newBalance=new_bal,
        timestamp=now.isoformat(),
        isSimulated=True,
        message=f"Please collect your simulated cash: ₹{payload.amount:,.2f}.",
    )


@router.post("/deposit", response_model=SimulatedTransactionResponse)
async def deposit_cash_simulated(
    payload: SimulatedTransactionRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """
    Simulated ATM cash deposit with atomic Firestore transaction.
    Adds funds to simulated account balance.
    """
    db = get_firestore_client()
    customer_id = current_customer["customerId"]
    cust_ref = db.collection("customers").document(customer_id)
    now = datetime.now(timezone.utc)

    # Atomic transactional deposit
    @gcloud_firestore.transactional
    def execute_deposit(transaction, ref, deposit_amount):
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="Customer record not found.")

        data = snapshot.to_dict()
        cur_balance = float(data.get("balance", settings.DEFAULT_INITIAL_BALANCE))
        updated_balance = round(cur_balance + deposit_amount, 2)

        transaction.update(ref, {
            "balance": updated_balance,
            "lastTransactionAt": now.isoformat(),
        })
        return cur_balance, updated_balance

    try:
        cur_bal, new_bal = execute_deposit(db.transaction(), cust_ref, payload.amount)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Deposit transaction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction processing error. Please try again.",
        )

    # Record completed transaction record
    txn_id = f"txn_d_{secrets.token_hex(12)}"
    txn_record = {
        "id": txn_id,
        "customerId": customer_id,
        "type": "DEPOSIT",
        "amount": payload.amount,
        "previousBalance": cur_bal,
        "newBalance": new_bal,
        "currency": "INR",
        "isSimulated": True,
        "status": "COMPLETED",
        "description": "Simulated ATM Cash Deposit",
        "timestamp": now.isoformat(),
    }

    db.collection("customers").document(customer_id).collection("transactions").document(txn_id).set(txn_record)
    db.collection("transactions").document(txn_id).set(txn_record)

    db.collection("audit_logs").add({
        "action": "ATM_DEPOSIT_SUCCESS",
        "customerId": customer_id,
        "transactionId": txn_id,
        "amount": payload.amount,
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return SimulatedTransactionResponse(
        success=True,
        transactionId=txn_id,
        type="DEPOSIT",
        amount=payload.amount,
        previousBalance=cur_bal,
        newBalance=new_bal,
        timestamp=now.isoformat(),
        isSimulated=True,
        message=f"Simulated deposit of ₹{payload.amount:,.2f} completed successfully.",
    )


@router.get("/transactions")
async def list_customer_transactions(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """
    Retrieve full transaction history for the authenticated customer.
    Customer isolation enforced; only current customer's records are accessed.
    """
    db = get_firestore_client()
    customer_id = current_customer["customerId"]

    txns = []
    try:
        txns_stream = (
            db.collection("customers")
            .document(customer_id)
            .collection("transactions")
            .order_by("timestamp", direction=gcloud_firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
        for t_doc in txns_stream:
            t_data = t_doc.to_dict()
            txns.append({
                "id": t_doc.id,
                "type": t_data.get("type"),
                "amount": float(t_data.get("amount", 0.0)),
                "previousBalance": float(t_data.get("previousBalance", 0.0)),
                "newBalance": float(t_data.get("newBalance", 0.0)),
                "timestamp": t_data.get("timestamp"),
                "status": t_data.get("status", "COMPLETED"),
                "description": t_data.get("description", "Simulated ATM Transaction"),
            })
    except Exception as exc:
        logger.error("Failed to query transaction list: %s", exc)

    return {"transactions": txns, "count": len(txns)}


@router.post("/logout")
async def logout_atm_customer(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
):
    """Invalidate current customer session immediately."""
    db = get_firestore_client()
    session_id = current_customer.get("sessionId")
    now = datetime.now(timezone.utc)

    if session_id:
        db.collection("customer_sessions").document(session_id).update({
            "active": False,
            "loggedOutAt": now.isoformat(),
        })

    db.collection("audit_logs").add({
        "action": "ATM_LOGOUT",
        "customerId": current_customer.get("customerId"),
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return {"success": True, "message": "ATM session ended successfully. Thank you for using Face ATM."}


# =====================================================================
# Card Owner Security Alert & Remote Verification Endpoints
# =====================================================================

@router.get("/security-alert/{incident_id}", response_model=OwnerIncidentDetailsResponse)
async def get_owner_security_alert_details(
    incident_id: str,
    token: str = Query(..., description="Signed HMAC owner decision token"),
):
    """
    Retrieve safe non-sensitive incident summary for card owner decision.
    Requires cryptographically valid, unexpired HMAC token linked to this incident.
    Does not expose sensitive credentials, embeddings, or full account data.
    """
    is_valid, tok_action, tok_cust = incident_storage.verify_owner_decision_token(incident_id, token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, forged, or expired security authorization token.",
        )

    db = get_firestore_client()
    approval_ref = db.collection("security_approvals").document(incident_id)
    approval_doc = approval_ref.get()

    if not approval_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security incident record was not found.",
        )

    data = approval_doc.to_dict()
    now = datetime.now(timezone.utc)

    # Check expiration
    expires_at_str = data.get("expiresAt")
    if expires_at_str and data.get("status") == "PENDING":
        try:
            exp_dt = datetime.fromisoformat(expires_at_str)
            if now > exp_dt:
                data["status"] = "EXPIRED"
                data["used"] = True
                approval_ref.update({"status": "EXPIRED", "used": True})
        except Exception:
            pass

    # Check live lockout state of customer
    is_locked = False
    lockout_remaining_seconds = 0
    cust_id = data.get("customerId")
    if cust_id:
        try:
            cust_doc = db.collection("customers").document(cust_id).get()
            if cust_doc.exists:
                c_dict = cust_doc.to_dict() or {}
                c_lock_until = c_dict.get("lockedUntil")
                if c_lock_until:
                    c_exp = datetime.fromisoformat(c_lock_until)
                    if now < c_exp:
                        is_locked = True
                        lockout_remaining_seconds = max(0, int((c_exp - now).total_seconds()))
        except Exception:
            pass

    return OwnerIncidentDetailsResponse(
        incidentId=data.get("id", incident_id),
        cardNumberMasked=data.get("cardNumberMasked", "•••• •••• •••• ••••"),
        customerName=data.get("customerName", "Card Owner"),
        attemptTimestamp=data.get("createdAt", now.isoformat()),
        status=data.get("status", "PENDING"),
        used=bool(data.get("used", False)),
        hasCapturedImage=bool(data.get("hasCapturedImage", False)),
        isLocked=is_locked,
        lockoutRemainingSeconds=lockout_remaining_seconds,
        message="Please verify if you recognize this login attempt and select ACCEPT or DENY.",
    )


@router.get("/security-alert/{incident_id}/image")
async def get_owner_security_alert_image(
    incident_id: str,
    token: str = Query(..., description="Signed HMAC owner decision or image access token"),
):
    """
    Securely fetch the captured failed-attempt image for the card owner.
    Access strictly restricted to valid token holders. Returns binary image with no-store headers.
    """
    # Verify owner token or image token
    is_valid_owner, _, _ = incident_storage.verify_owner_decision_token(incident_id, token)
    is_valid_img = incident_storage.verify_image_access_token(incident_id, token)

    if not is_valid_owner and not is_valid_img:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. A valid signed authorization token is required to view this image.",
        )

    db = get_firestore_client()
    result = incident_storage.get_incident_image(incident_id, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident captured image not found or has been purged.",
        )

    img_bytes, mime_type = result
    return Response(
        content=img_bytes,
        media_type=mime_type,
        headers={
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/security-alert/{incident_id}/decision")
async def process_owner_alert_decision(
    incident_id: str,
    payload: OwnerAlertDecisionRequest,
):
    """
    Card owner ACCEPT or DENY response to a security incident alert.
    Validates token authenticity, expiration, and replay protection.
    - ACCEPT: Authenticated response lifts card lockout so customer can retry. Customer MUST still pass face verification before transactions are permitted.
    - DENY: Blocks login attempt and maintains security lockout.
    """
    is_valid, tok_action, tok_cust = incident_storage.verify_owner_decision_token(
        incident_id, payload.token, expected_action=payload.decision
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, forged, or expired authorization token.",
        )

    decision = payload.decision.upper().strip()
    db = get_firestore_client()
    approval_ref = db.collection("security_approvals").document(incident_id)
    approval_doc = approval_ref.get()

    if not approval_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security incident not found.",
        )

    data = approval_doc.to_dict()
    now = datetime.now(timezone.utc)

    # Replay protection: check if already used or finalized
    if data.get("used") or data.get("status") != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This security incident has already been finalized (status: {data.get('status')}).",
        )

    # Validate expiration
    expires_at_str = data.get("expiresAt")
    if expires_at_str:
        try:
            exp_dt = datetime.fromisoformat(expires_at_str)
            if now > exp_dt:
                approval_ref.update({"status": "EXPIRED", "used": True})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This security approval request has expired and cannot be modified.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    customer_id = data.get("customerId") or tok_cust
    card_masked = data.get("cardNumberMasked", "")

    if decision == "ACCEPT":
        # Finalize approval document
        approval_ref.update({
            "status": "ACCEPTED",
            "used": True,
            "decision": "ACCEPT",
            "decidedBy": "CARD_OWNER",
            "decidedAt": now.isoformat(),
        })

        # Lift customer lockout so customer can retry facial verification
        if customer_id:
            cust_ref = db.collection("customers").document(customer_id)
            cust_ref.update({
                "lockedUntil": None,
                "failedAttempts": 0,
                "unlockedByOwner": True,
                "unlockedAt": now.isoformat(),
            })

        db.collection("audit_logs").add({
            "action": "ATM_OWNER_ALERT_ACCEPTED",
            "incidentId": incident_id,
            "customerId": customer_id,
            "cardNumberMasked": card_masked,
            "timestamp": now.isoformat(),
            "status": "ACCEPTED",
        })

        return {
            "success": True,
            "status": "ACCEPTED",
            "incidentId": incident_id,
            "message": "Alert accepted. Card lockout has been cleared. The customer must still pass facial biometric verification at the ATM terminal before transactions are permitted.",
        }
    else:
        # Finalize as DENIED
        approval_ref.update({
            "status": "DENIED",
            "used": True,
            "decision": "DENY",
            "decidedBy": "CARD_OWNER",
            "decidedAt": now.isoformat(),
        })

        # Ensure lockout remains in effect
        db.collection("audit_logs").add({
            "action": "ATM_OWNER_ALERT_DENIED",
            "incidentId": incident_id,
            "customerId": customer_id,
            "cardNumberMasked": card_masked,
            "timestamp": now.isoformat(),
            "status": "DENIED",
        })

        return {
            "success": True,
            "status": "DENIED",
            "incidentId": incident_id,
            "message": "Login attempt denied. The card remains locked to protect your account.",
        }


@router.get("/security-alert/{incident_id}/decision", response_class=HTMLResponse)
async def process_owner_alert_decision_get(
    incident_id: str,
    token: str = Query(..., description="Signed HMAC owner decision token"),
    decision: str = Query(..., description="'ACCEPT' or 'DENY'"),
):
    """
    Direct browser link handler for card owners clicking ACCEPT or DENY from email clients.
    Renders a secure, responsive confirmation page with bank styling.
    """
    clean_decision = decision.upper().strip()
    if clean_decision not in ("ACCEPT", "DENY"):
        return HTMLResponse(
            content="<h2>Invalid decision parameter. Must be ACCEPT or DENY.</h2>",
            status_code=400,
        )

    try:
        req = OwnerAlertDecisionRequest(token=token, decision=clean_decision)
        res = await process_owner_alert_decision(incident_id, req)
        success = True
        title = "Authorization Accepted" if clean_decision == "ACCEPT" else "Attempt Blocked"
        badge_color = "#059669" if clean_decision == "ACCEPT" else "#dc2626"
        msg = res["message"]
    except HTTPException as exc:
        success = False
        title = "Action Could Not Be Completed"
        badge_color = "#d97706"
        msg = exc.detail
    except Exception as exc:
        success = False
        title = "Unexpected Error"
        badge_color = "#dc2626"
        msg = str(exc)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Face ATM Security Decision | {title}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; display: flex; justify-content: center; align-items: center; min-height: 100vh; box-sizing: border-box; }}
        .card {{ background: #1e293b; border-radius: 14px; max-width: 520px; width: 100%; padding: 32px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 25px rgba(0,0,0,0.5); text-align: center; }}
        .badge {{ display: inline-block; background-color: {badge_color}; color: #ffffff; padding: 6px 16px; border-radius: 999px; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 16px; }}
        h1 {{ font-size: 22px; margin: 0 0 14px; font-weight: 800; }}
        p {{ color: #cbd5e1; font-size: 14px; line-height: 1.6; margin: 0 0 24px; }}
        .btn {{ display: inline-block; background-color: #3b82f6; color: #ffffff; padding: 12px 28px; border-radius: 8px; font-weight: 600; text-decoration: none; font-size: 14px; }}
        .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <span class="badge">{title}</span>
        <h1>Face ATM Security Alert</h1>
        <p>{msg}</p>
        <a href="http://localhost:5173/atm" class="btn">Return to ATM Terminal</a>
        <div class="footer">&copy; 2026 Face ATM — Biometric Security & Account Protection</div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200 if success else 400)
