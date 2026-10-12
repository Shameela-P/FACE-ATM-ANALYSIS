"""Security dependencies and authentication verification for administrative routes."""

import logging
from typing import Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.firebase import verify_firebase_token, is_firebase_admin_ready, get_firestore_client

logger = logging.getLogger("face_atm.security")

# Reusable HTTP Bearer security scheme
security_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Authenticate and authorize an incoming administrative request.

    Requirements:
    1. Bearer token must be provided in Authorization header.
    2. Token must be a valid, unexpired Firebase ID token.
    3. The authenticated user must match the operational ADMIN role
       (matching ADMIN_EMAIL or having custom claim admin=True).

    Raises:
        HTTPException 401 if token is missing or invalid.
        HTTPException 403 if the user is authenticated but not an admin.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not is_firebase_admin_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication verification service is not ready. Verify server Firebase credentials.",
        )

    try:
        claims = verify_firebase_token(token)
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_email = claims.get("email", "").lower()
    is_claim_admin = claims.get("admin") is True
    configured_admin_email = settings.ADMIN_EMAIL.lower()

    # Enforce strictly the single operational admin role
    is_admin = is_claim_admin or (user_email and user_email == configured_admin_email)

    if not is_admin:
        logger.warning("Unauthorized access attempt by non-admin user: %s", user_email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: Administrative privileges required.",
        )

    return {
        "uid": claims.get("uid"),
        "email": user_email,
        "role": "ADMIN",
        "auth_time": claims.get("auth_time"),
    }


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Authenticate and authorize an incoming customer ATM session.

    Requirements:
    1. Bearer session token must be provided in Authorization header.
    2. Session token must exist in 'customer_sessions' collection in Firestore.
    3. Session must be active and not expired.
    4. Associated customer account must be in 'ACTIVE' status.

    Raises:
        HTTPException 401 if token is missing, invalid, or expired.
        HTTPException 403 if the customer account is locked/inactive.
    """
    from datetime import datetime, timezone

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer authentication session token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    db = get_firestore_client()

    session_ref = db.collection("customer_sessions").document(token)
    session_doc = session_ref.get()

    if not session_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer session is invalid or expired. Please re-authenticate at the terminal.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_data = session_doc.to_dict()

    if not session_data.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer session has been signed out. Please authenticate at the terminal.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    expires_at_str = session_data.get("expiresAt")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if now > expires_at:
                # Mark session inactive
                session_ref.update({"active": False})
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Customer session expired. Please re-authenticate with your face at the terminal.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception:
            pass

    customer_id = session_data.get("customerId")
    cust_doc = db.collection("customers").document(customer_id).get()

    if not cust_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    cust_data = cust_doc.to_dict()

    if cust_data.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account is suspended or inactive. Please contact bank administration.",
        )

    return {
        "customerId": customer_id,
        "fullName": cust_data.get("fullName", session_data.get("fullName", "Customer")),
        "cardNumberMasked": cust_data.get("cardNumberMasked", session_data.get("cardNumberMasked")),
        "email": cust_data.get("email"),
        "bankName": cust_data.get("bankName", "Face ATM"),
        "status": cust_data.get("status"),
        "sessionId": token,
    }

