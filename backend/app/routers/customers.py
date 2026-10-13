"""Customer registration, email OTP verification, biometric face enrollment, and card issuance router."""

import re
import base64
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_admin
from app.core.firebase import get_firestore_client
from app.core.config import settings
from app.core.crypto import (
    encrypt_sensitive_data,
    hash_deterministic,
    mask_aadhaar,
    mask_bank_account,
    mask_card_number,
    format_card_number_display,
    generate_secure_otp,
    generate_salt,
    hash_otp,
    verify_otp_constant_time,
    generate_unique_card_number,
)
from app.services.email_service import email_service
from app.services.face_service import face_service, FaceProcessingError
from app.schemas.customer import (
    CustomerRegistrationRequest,
    RegistrationInitiateResponse,
    OTPResendRequest,
    OTPVerifyRequest,
    OTPVerifyResponse,
    FaceEnrollmentRequest,
    FaceEnrollmentResponse,
    ResendCardEmailRequest,
    CustomerListItem,
)

logger = logging.getLogger("face_atm.customers")
router = APIRouter(prefix="/api/customers", tags=["Customers"])


def _mask_phone(phone: str) -> str:
    clean = re.sub(r"\D", "", phone)
    if len(clean) >= 4:
        return f"{'X' * (len(clean) - 4)}{clean[-4:]}"
    return "XXXXXXXXXX"


@router.post("/register-initiate", response_model=RegistrationInitiateResponse)
async def initiate_customer_registration(
    payload: CustomerRegistrationRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Validate customer registration data, check for duplicate records,
    generate cryptographically secure OTP, and send verification email.
    """
    db = get_firestore_client()

    # 1. Compute deterministic keyed HMAC hashes for duplicate detection without exposing PII
    email_hash = hash_deterministic(payload.email, "email")
    phone_hash = hash_deterministic(payload.phone, "phone")
    aadhaar_hash = hash_deterministic(payload.aadhaarNumber, "aadhaar")
    bank_hash = hash_deterministic(payload.bankAccountNumber, "bank_account")

    # 2. Check for duplicate customer records in Firestore
    customers_col = db.collection("customers")

    dup_email = customers_col.where("email_hash", "==", email_hash).limit(1).get()
    if len(dup_email) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer is already registered with this email address.",
        )

    dup_phone = customers_col.where("phone_hash", "==", phone_hash).limit(1).get()
    if len(dup_phone) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer is already registered with this phone number.",
        )

    dup_aadhaar = customers_col.where("aadhaar_hash", "==", aadhaar_hash).limit(1).get()
    if len(dup_aadhaar) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer is already registered with this Aadhaar number.",
        )

    dup_bank = customers_col.where("bankAccount_hash", "==", bank_hash).limit(1).get()
    if len(dup_bank) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer is already registered with this bank account number.",
        )

    # 3. Generate secure OTP and session salt
    otp_code = generate_secure_otp(6)
    salt = generate_salt(16)
    otp_hash_val = hash_otp(otp_code, salt)
    verification_id = f"vrf_{secrets.token_hex(16)}"

    # 4. Encrypt sensitive PII using AES-256-GCM
    aadhaar_encrypted = encrypt_sensitive_data(payload.aadhaarNumber)
    bank_encrypted = encrypt_sensitive_data(payload.bankAccountNumber)

    aadhaar_masked = mask_aadhaar(payload.aadhaarNumber)
    bank_masked = mask_bank_account(payload.bankAccountNumber)
    phone_masked = _mask_phone(payload.phone)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    customer_summary = {
        "fullName": payload.fullName,
        "email": payload.email,
        "phoneMasked": phone_masked,
        "dob": payload.dob,
        "aadhaarMasked": aadhaar_masked,
        "bankName": payload.bankName,
        "bankAccountMasked": bank_masked,
    }

    # 5. Persist verification session document in Firestore
    verification_data = {
        "id": verification_id,
        "email": payload.email,
        "email_hash": email_hash,
        "otp_hash": otp_hash_val,
        "salt": salt,
        "customer_draft": {
            "fullName": payload.fullName,
            "email": payload.email,
            "phone": payload.phone,
            "dob": payload.dob,
            "bankName": payload.bankName,
            "aadhaar_encrypted": aadhaar_encrypted,
            "aadhaar_mask": aadhaar_masked,
            "aadhaar_hash": aadhaar_hash,
            "bankAccount_encrypted": bank_encrypted,
            "bankAccount_mask": bank_masked,
            "bankAccount_hash": bank_hash,
            "email_hash": email_hash,
            "phone_hash": phone_hash,
            "phone_mask": phone_masked,
        },
        "customer_summary": customer_summary,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "max_attempts": settings.OTP_MAX_ATTEMPTS,
        "last_resent_at": now.isoformat(),
        "verified": False,
        "completed": False,
        "admin_uid": current_admin.get("uid"),
    }

    db.collection("otp_verifications").document(verification_id).set(verification_data)

    # 6. Audit logging (without sensitive customer PII)
    db.collection("audit_logs").add({
        "action": "CUSTOMER_REGISTRATION_INITIATED",
        "verificationId": verification_id,
        "adminUid": current_admin.get("uid"),
        "adminEmail": current_admin.get("email"),
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    # 7. Dispatch OTP via Gmail SMTP email service
    email_delivery = await email_service.send_otp_email(
        recipient_email=payload.email,
        recipient_name=payload.fullName,
        otp_code=otp_code,
        expiry_minutes=settings.OTP_EXPIRY_MINUTES,
    )

    delivered = bool(email_delivery.get("delivered"))
    msg = (
        f"Verification code sent to {payload.email}."
        if delivered
        else f"Failed to deliver verification code: {email_delivery.get('error', 'Delivery failed')}."
    )

    return RegistrationInitiateResponse(
        verificationId=verification_id,
        email=payload.email,
        customerSummary=customer_summary,
        expiresInSeconds=settings.OTP_EXPIRY_MINUTES * 60,
        cooldownSeconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        emailDelivery=email_delivery,
        message=msg,
    )


@router.post("/otp-resend")
async def resend_customer_otp(
    payload: OTPResendRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Resend verification OTP subject to cooldown restrictions and attempt tracking.
    """
    db = get_firestore_client()
    session_ref = db.collection("otp_verifications").document(payload.verificationId)
    session_doc = session_ref.get()

    if not session_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found or expired.",
        )

    session_data = session_doc.to_dict()

    if session_data.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address for this registration has already been verified.",
        )

    if session_data.get("completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This registration session has already been completed.",
        )

    # Enforce resend cooldown
    now = datetime.now(timezone.utc)
    last_resent_str = session_data.get("last_resent_at")
    if last_resent_str:
        try:
            last_resent = datetime.fromisoformat(last_resent_str)
            elapsed = (now - last_resent).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new code.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    # Generate new random OTP and salt
    otp_code = generate_secure_otp(6)
    salt = generate_salt(16)
    otp_hash_val = hash_otp(otp_code, salt)
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    session_ref.update({
        "otp_hash": otp_hash_val,
        "salt": salt,
        "expires_at": expires_at.isoformat(),
        "last_resent_at": now.isoformat(),
        "attempts": 0,  # Reset attempts on fresh OTP
    })

    # Send new email
    customer_draft = session_data.get("customer_draft", {})
    recipient_email = session_data.get("email")
    recipient_name = customer_draft.get("fullName", "Customer")

    email_delivery = await email_service.send_otp_email(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        otp_code=otp_code,
        expiry_minutes=settings.OTP_EXPIRY_MINUTES,
    )

    delivered = bool(email_delivery.get("delivered"))
    return {
        "success": delivered,
        "expiresInSeconds": settings.OTP_EXPIRY_MINUTES * 60,
        "cooldownSeconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
        "emailDelivery": email_delivery,
        "message": (
            f"A new verification code has been dispatched to {recipient_email}."
            if delivered
            else f"Failed to dispatch verification code: {email_delivery.get('error', 'Delivery failed')}."
        ),
    }


@router.post("/otp-verify", response_model=OTPVerifyResponse)
async def verify_customer_otp(
    payload: OTPVerifyRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Verify customer OTP using constant-time comparison.
    Invalidates code upon success and enforces attempt limits.
    """
    db = get_firestore_client()
    session_ref = db.collection("otp_verifications").document(payload.verificationId)
    session_doc = session_ref.get()

    if not session_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found or expired.",
        )

    session_data = session_doc.to_dict()

    if session_data.get("verified"):
        return OTPVerifyResponse(
            verified=True,
            verificationId=payload.verificationId,
            customerSummary=session_data.get("customer_summary", {}),
            message="Email already verified. You may proceed to face enrollment.",
        )

    now = datetime.now(timezone.utc)
    expires_at_str = session_data.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new code.",
            )

    attempts = session_data.get("attempts", 0)
    max_attempts = session_data.get("max_attempts", settings.OTP_MAX_ATTEMPTS)

    if attempts >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please restart registration.",
        )

    # Constant-time verification
    salt = session_data.get("salt", "")
    expected_hash = session_data.get("otp_hash", "")
    is_valid = verify_otp_constant_time(payload.otp, salt, expected_hash)

    if not is_valid:
        new_attempts = attempts + 1
        session_ref.update({"attempts": new_attempts})
        remaining = max_attempts - new_attempts
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Maximum attempts reached. Session invalidated.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
        )

    # Valid OTP: Invalidate OTP immediately and record verification
    session_ref.update({
        "verified": True,
        "verified_at": now.isoformat(),
        "otp_hash": "",  # Invalidate OTP hash to prevent replay
    })

    db.collection("audit_logs").add({
        "action": "OTP_VERIFICATION_SUCCESS",
        "verificationId": payload.verificationId,
        "adminUid": current_admin.get("uid"),
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    return OTPVerifyResponse(
        verified=True,
        verificationId=payload.verificationId,
        customerSummary=session_data.get("customer_summary", {}),
        message="Email successfully verified. Proceed to biometric face enrollment.",
    )


@router.post("/enroll-face", response_model=FaceEnrollmentResponse)
async def enroll_customer_face(
    payload: FaceEnrollmentRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Process biometric facial capture, extract 128-dim embedding, create customer record,
    generate unique card number, and notify customer via email.
    """
    db = get_firestore_client()
    session_ref = db.collection("otp_verifications").document(payload.verificationId)
    session_doc = session_ref.get()

    if not session_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration session not found.",
        )

    session_data = session_doc.to_dict()

    if not session_data.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification must be completed before biometric face enrollment.",
        )

    if session_data.get("completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This registration session has already been completed.",
        )

    if not payload.consentObtained:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit customer consent is required before capturing biometric face data.",
        )

    # Decode base64 image
    raw_b64 = payload.imageBase64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image data: {exc}",
        )

    # Process face and extract 128-dimensional embedding
    try:
        face_result = face_service.process_and_extract_embedding(
            image_bytes=image_bytes,
            consent_obtained=payload.consentObtained,
        )
    except FaceProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error("Face enrollment unexpected error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Generate unique 16-digit card number with safe collision handling
    card_number = None
    cards_col = db.collection("cards")
    for _ in range(10):
        candidate_card = generate_unique_card_number()
        card_check = cards_col.document(candidate_card).get()
        if not card_check.exists:
            card_number = candidate_card
            break

    if not card_number:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate a unique card number. Please try again.",
        )

    # Assemble customer record
    customer_draft = session_data.get("customer_draft", {})
    customer_id = f"cust_{secrets.token_hex(12)}"
    now = datetime.now(timezone.utc)
    card_masked = mask_card_number(card_number)
    formatted_card = format_card_number_display(card_number)

    customer_doc_data = {
        "id": customer_id,
        "fullName": customer_draft.get("fullName"),
        "email": customer_draft.get("email"),
        "phoneMasked": customer_draft.get("phone_mask"),
        "phone_hash": customer_draft.get("phone_hash"),
        "email_hash": customer_draft.get("email_hash"),
        "dob": customer_draft.get("dob"),
        "bankName": customer_draft.get("bankName"),
        "aadhaar_mask": customer_draft.get("aadhaar_mask"),
        "aadhaar_hash": customer_draft.get("aadhaar_hash"),
        "aadhaar_encrypted": customer_draft.get("aadhaar_encrypted"),
        "bankAccount_mask": customer_draft.get("bankAccount_mask"),
        "bankAccount_hash": customer_draft.get("bankAccount_hash"),
        "bankAccount_encrypted": customer_draft.get("bankAccount_encrypted"),
        "cardNumber": card_number,
        "cardNumberMasked": card_masked,
        "cardNumber_hash": hash_deterministic(card_number, "card"),
        "emailVerified": True,
        "faceEnrolled": True,
        "status": "ACTIVE",
        "createdAt": now.isoformat(),
        "createdBy": current_admin.get("uid"),
    }

    # Save customer, biometric face embedding, card registration, and mark session completed
    batch = db.batch()

    # 1. Customer record
    cust_ref = db.collection("customers").document(customer_id)
    batch.set(cust_ref, customer_doc_data)

    # 2. Biometric face embedding subcollection (Never stores raw image)
    biometrics_ref = cust_ref.collection("biometrics").document("face")
    batch.set(biometrics_ref, {
        "customerId": customer_id,
        "embedding": face_result["embedding"],
        "dimensions": face_result["dimensions"],
        "confidence": face_result["confidence"],
        "model": face_result["model"],
        "detector": face_result["detector"],
        "consentObtained": True,
        "consentTimestamp": face_result["consent_timestamp"],
        "enrolledAt": now.isoformat(),
        "livenessChecked": False,
    })

    # 3. Card uniqueness lookup
    card_ref = cards_col.document(card_number)
    batch.set(card_ref, {
        "cardNumber": card_number,
        "customerId": customer_id,
        "status": "ACTIVE",
        "issuedAt": now.isoformat(),
        "createdBy": current_admin.get("uid"),
    })

    # 4. Mark verification session completed
    batch.update(session_ref, {
        "completed": True,
        "customerId": customer_id,
        "completedAt": now.isoformat(),
    })

    # Commit batch
    batch.commit()

    # Record operational audit log
    db.collection("audit_logs").add({
        "action": "CUSTOMER_ENROLLED_AND_CARD_ISSUED",
        "customerId": customer_id,
        "adminUid": current_admin.get("uid"),
        "adminEmail": current_admin.get("email"),
        "timestamp": now.isoformat(),
        "status": "SUCCESS",
    })

    # Send card notification email
    email_delivery = await email_service.send_card_issued_email(
        recipient_email=customer_draft.get("email"),
        recipient_name=customer_draft.get("fullName"),
        card_number=card_number,
    )

    # Update customer record with email delivery status
    cust_ref.update({
        "cardEmailDelivered": email_delivery.get("delivered", False),
        "cardEmailDeliveryId": email_delivery.get("id"),
    })

    return FaceEnrollmentResponse(
        customerId=customer_id,
        fullName=customer_draft.get("fullName"),
        email=customer_draft.get("email"),
        cardNumber=formatted_card,
        cardNumberMasked=card_masked,
        faceEnrolled=True,
        confidence=face_result["confidence"],
        emailDelivery=email_delivery,
        message="Customer registration and biometric enrollment completed successfully.",
    )


@router.post("/resend-card-email")
async def resend_customer_card_email(
    payload: ResendCardEmailRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Safely retry sending customer card details email in case of initial delivery issues.
    """
    db = get_firestore_client()
    cust_doc = db.collection("customers").document(payload.customerId).get()

    if not cust_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer record not found.",
        )

    cust_data = cust_doc.to_dict()
    card_number = cust_data.get("cardNumber")
    recipient_email = cust_data.get("email")
    recipient_name = cust_data.get("fullName", "Customer")

    if not card_number or not recipient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer record is missing card number or email.",
        )

    delivery = await email_service.send_card_issued_email(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        card_number=card_number,
    )

    cust_doc.reference.update({
        "cardEmailDelivered": delivery.get("delivered", False),
        "cardEmailDeliveryId": delivery.get("id"),
        "lastCardEmailResentAt": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "success": True,
        "delivered": delivery.get("delivered", False),
        "error": delivery.get("error"),
        "message": "Card notification email dispatch triggered.",
    }


@router.get("", response_model=List[CustomerListItem])
async def list_registered_customers(
    limit: int = 50,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Retrieve registered customer list with non-sensitive fields for administrative overview.
    Strictly excludes Aadhaar numbers, full bank account numbers, and biometric vectors.
    """
    db = get_firestore_client()
    query = db.collection("customers").order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = query.get()

    results: List[CustomerListItem] = []
    for doc in docs:
        data = doc.to_dict()
        results.append(
            CustomerListItem(
                id=data.get("id", doc.id),
                fullName=data.get("fullName", "Unknown"),
                email=data.get("email", ""),
                phoneMasked=data.get("phoneMasked", "XXXXXXXXXX"),
                cardNumberMasked=data.get("cardNumberMasked", "XXXX-XXXX-XXXX-XXXX"),
                bankName=data.get("bankName", "Unknown"),
                bankAccountMasked=data.get("bankAccount_mask", "XXXXXXXXXXXX"),
                status=data.get("status", "ACTIVE"),
                createdAt=data.get("createdAt", ""),
                faceEnrolled=data.get("faceEnrolled", False),
            )
        )

    return results
