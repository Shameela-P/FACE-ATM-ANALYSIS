from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.security import get_current_admin, security_scheme
from app.core.firebase import get_firestore_client, verify_firebase_token
from app.services.email_service import email_service
from app.services.incident_storage import incident_storage

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/test-smtp")
async def test_smtp_configuration(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Safely probe Gmail SMTP connection and authentication.
    Requires authenticated administrator credentials. Does not expose passwords.
    """
    result = await email_service.test_connection()
    return result



@router.get("/verify")
async def verify_admin_session(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Verify administrative authentication token and credentials.
    Protected: Requires a valid Firebase ID token for an authorized administrator.
    """
    return {
        "status": "authorized",
        "role": current_admin.get("role"),
        "email": current_admin.get("email"),
        "uid": current_admin.get("uid"),
    }


@router.get("/summary")
async def get_dashboard_summary(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Retrieve operational summary counts for the administrative dashboard.
    In Phase 3, queries live customer, face enrollment, and transaction counts from Firestore.
    """
    customers_count = 0
    verifications_count = 0
    transactions_count = 0
    pending_approvals_count = 0

    try:
        db = get_firestore_client()
        # Query active customers and enrollments count
        for doc in db.collection("customers").stream():
            customers_count += 1
            if doc.to_dict().get("faceEnrolled"):
                verifications_count += 1

        # Query simulated transactions count
        for _ in db.collection("transactions").stream():
            transactions_count += 1

        # Query pending approvals count
        for doc in db.collection("security_approvals").stream():
            d = doc.to_dict()
            if d.get("status") == "PENDING" and not d.get("used"):
                pending_approvals_count += 1
    except Exception:
        pass

    return {
        "customers_count": customers_count,
        "verifications_count": verifications_count,
        "transactions_count": transactions_count,
        "pending_approvals_count": pending_approvals_count,
        "phase": 3,
        "message": "Phase 3 active with live customer face login, simulated ATM transactions, and security approvals.",
    }


@router.get("/security-approvals")
async def list_security_approvals(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    List security approval requests for review by authorized administrators.
    Automatically checks and marks expired requests.
    Includes lockout status and captured incident image indicators.
    """
    from datetime import datetime, timezone

    db = get_firestore_client()
    now = datetime.now(timezone.utc)
    approvals = []

    try:
        stream = db.collection("security_approvals").stream()
        for doc in stream:
            data = doc.to_dict()
            # Check expiration
            expires_at_str = data.get("expiresAt")
            if expires_at_str and data.get("status") == "PENDING":
                try:
                    exp_dt = datetime.fromisoformat(expires_at_str)
                    if now > exp_dt:
                        data["status"] = "EXPIRED"
                        data["used"] = True
                        doc.reference.update({"status": "EXPIRED", "used": True})
                except Exception:
                    pass

            # Determine live customer lockout state
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

            approvals.append({
                "id": data.get("id", doc.id),
                "customerId": data.get("customerId"),
                "customerName": data.get("customerName", "Customer"),
                "customerEmail": data.get("customerEmail", ""),
                "cardNumberMasked": data.get("cardNumberMasked", ""),
                "reason": data.get("reason", "Face verification mismatch"),
                "failedAttempts": data.get("failedAttempts", 3),
                "status": data.get("status", "PENDING"),
                "createdAt": data.get("createdAt", now.isoformat()),
                "expiresAt": data.get("expiresAt", now.isoformat()),
                "reviewedBy": data.get("reviewedBy"),
                "reviewedAt": data.get("reviewedAt"),
                "notes": data.get("notes"),
                "hasCapturedImage": data.get("hasCapturedImage", False),
                "imageContentType": data.get("imageContentType", "image/jpeg"),
                "imageSizeBytes": data.get("imageSizeBytes"),
                "isLocked": is_locked,
                "lockoutRemainingSeconds": lockout_remaining_seconds,
            })
    except Exception as exc:
        pass

    # Sort descending by creation timestamp
    approvals.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return {"approvals": approvals, "count": len(approvals)}


@router.get("/security-approvals/{approval_id}/image-token")
async def get_incident_image_token(
    approval_id: str,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Generate a short-lived (5-minute) signed HMAC token for viewing a security incident image.
    Requires authenticated administrator credentials.
    """
    db = get_firestore_client()
    approval_doc = db.collection("security_approvals").document(approval_id).get()
    if not approval_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security approval request not found.",
        )

    admin_email = current_admin.get("email", "admin")
    token = incident_storage.generate_image_access_token(
        approval_id=approval_id,
        admin_email=admin_email,
        expiry_seconds=300,
    )
    return {
        "approvalId": approval_id,
        "token": token,
        "expiresInSeconds": 300,
    }


@router.get("/security-approvals/{approval_id}/image")
async def get_security_approval_image(
    approval_id: str,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
):
    """
    Securely fetch the captured failed-attempt image for an incident.
    Access is strictly restricted to:
    1. Authorized administrator with Bearer token, OR
    2. Signed short-lived HMAC token passed as query param or bearer token.
    Returns the binary image with no-cache headers.
    """
    is_authorized = False

    # Check 1: Short-lived signed HMAC token
    if token and incident_storage.verify_image_access_token(approval_id, token):
        is_authorized = True

    # Check 2: Bearer token in Authorization header
    if not is_authorized and credentials and credentials.credentials:
        try:
            # Check if bearer token is short-lived HMAC token
            if incident_storage.verify_image_access_token(approval_id, credentials.credentials):
                is_authorized = True
            else:
                # Validate as Firebase Admin token
                claims = verify_firebase_token(credentials.credentials)
                user_email = claims.get("email", "").lower()
                is_claim_admin = claims.get("admin") is True
                configured_admin_email = settings.ADMIN_EMAIL.lower()
                if is_claim_admin or (configured_admin_email and user_email == configured_admin_email):
                    is_authorized = True
        except Exception:
            pass

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. A valid administrator session or short-lived incident token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = get_firestore_client()
    approval_doc = db.collection("security_approvals").document(approval_id).get()
    if not approval_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security approval request not found.",
        )

    result = incident_storage.get_incident_image(approval_id, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident captured image not found or has been purged according to retention policy.",
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


@router.post("/security-approvals/{approval_id}/decision")
async def process_security_approval_decision(
    approval_id: str,
    payload: Dict[str, Any],
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Authorized administrator Accept or Deny action on a single-use security approval request.
    Validates expiration, prevents reuse, and records the reviewing administrator.
    Accepting resets the customer lockout so they can retry face verification at the ATM terminal.
    """
    from datetime import datetime, timezone
    from fastapi import HTTPException, status

    decision = str(payload.get("decision", "")).strip().upper()
    notes = payload.get("notes", "")

    if decision not in ("ACCEPT", "DENY"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be either 'ACCEPT' or 'DENY'.",
        )

    db = get_firestore_client()
    approval_ref = db.collection("security_approvals").document(approval_id)
    approval_doc = approval_ref.get()

    if not approval_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security approval request not found.",
        )

    data = approval_doc.to_dict()
    now = datetime.now(timezone.utc)

    # Validate single-use & status
    if data.get("used") or data.get("status") != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request has already been finalized (status: {data.get('status')}).",
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

    reviewer_email = current_admin.get("email", "admin")
    reviewer_uid = current_admin.get("uid", "")
    customer_id = data.get("customerId")

    if decision == "ACCEPT":
        # Finalize approval document
        approval_ref.update({
            "status": "ACCEPTED",
            "used": True,
            "reviewedBy": reviewer_email,
            "reviewedByUid": reviewer_uid,
            "reviewedAt": now.isoformat(),
            "notes": notes,
        })

        # Lift customer lockout so customer can retry face verification at ATM
        if customer_id:
            cust_ref = db.collection("customers").document(customer_id)
            cust_ref.update({
                "lockedUntil": None,
                "failedAttempts": 0,
                "unlockedByAdmin": reviewer_email,
                "unlockedAt": now.isoformat(),
            })

        db.collection("audit_logs").add({
            "action": "ADMIN_SECURITY_APPROVAL_ACCEPTED",
            "approvalId": approval_id,
            "customerId": customer_id,
            "adminEmail": reviewer_email,
            "timestamp": now.isoformat(),
            "status": "SUCCESS",
        })

        return {
            "success": True,
            "status": "ACCEPTED",
            "message": "Security approval accepted. Customer lockout lifted. Customer can now retry face verification.",
        }
    else:
        # Finalize as DENIED
        approval_ref.update({
            "status": "DENIED",
            "used": True,
            "reviewedBy": reviewer_email,
            "reviewedByUid": reviewer_uid,
            "reviewedAt": now.isoformat(),
            "notes": notes,
        })

        db.collection("audit_logs").add({
            "action": "ADMIN_SECURITY_APPROVAL_DENIED",
            "approvalId": approval_id,
            "customerId": customer_id,
            "adminEmail": reviewer_email,
            "timestamp": now.isoformat(),
            "status": "DENIED",
        })

        return {
            "success": True,
            "status": "DENIED",
            "message": "Security approval denied. Customer lockout remains active.",
        }

