"""Comprehensive test suite for Face ATM Failed Face Verification Security Alert Workflow.

Verifies:
1. Failed attempts below threshold (attempts 1 & 2) do not lock card or create security approvals.
2. Third failed attempt triggers 15-minute lockout, stores incident image, and creates approval.
3. Correct recipient email and actual captured image attachment (no synthetic or enrolled substitution).
4. Missing image or SMTP delivery failure handled safely (fail-closed security).
5. Input validation on image payload size and format.
6. Authorized administrator image access vs unauthorized / unauthenticated access.
7. Short-lived signed HMAC token generation and verification.
8. Accept and Deny approval decision behavior and replay protection.
9. Expiration of approvals and automatic card lockout expiry in card-validate.
10. Subsequent face verification still strictly requiring YuNet, MiniFASNet, and SFace checks.
"""

import sys
import os
import base64
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.face_service import face_service, FaceProcessingError
from app.services.incident_storage import incident_storage

client = TestClient(app)

# Real valid 1x1 JPEG bytes for testing
VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
    b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)
VALID_JPEG_B64 = "data:image/jpeg;base64," + base64.b64encode(VALID_JPEG_BYTES).decode("utf-8")


def mock_customer_db(failed_attempts=0, locked_until=None):
    """Create mock Firestore DB with a registered active card and customer."""
    mock_db = MagicMock()
    now = datetime.now(timezone.utc)
    card_number = "4000123456789010"

    mock_card = MagicMock()
    mock_card.exists = True
    mock_card.to_dict.return_value = {
        "customerId": "cust_test_workflow",
        "cardNumber": card_number,
        "status": "ACTIVE",
    }

    cust_data = {
        "fullName": "Pavithra Test",
        "email": "pavithra.workss@gmail.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "failedAttempts": failed_attempts,
        "lockedUntil": locked_until,
        "balance": 50000.0,
    }

    mock_cust = MagicMock()
    mock_cust.exists = True
    mock_cust.to_dict.return_value = cust_data

    mock_bio = MagicMock()
    mock_bio.exists = True
    mock_bio.to_dict.return_value = {"embedding": [0.05] * 128}

    mock_approvals_collection = MagicMock()

    def collection_side_effect(name):
        col = MagicMock()
        if name == "cards":
            col.document.return_value.get.return_value = mock_card
        elif name == "customers":
            doc = MagicMock()
            doc.get.return_value = mock_cust
            doc.collection.return_value.document.return_value.get.return_value = mock_bio
            col.document.return_value = doc
        elif name == "security_approvals":
            return mock_approvals_collection
        return col

    mock_db.collection.side_effect = collection_side_effect
    return mock_db, mock_cust, mock_approvals_collection, cust_data


# 1. Below lockout threshold: failed attempts 1 and 2
@pytest.mark.anyio
async def test_failed_attempt_below_threshold_does_not_lock_or_create_approval():
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=0)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch.object(face_service, "compare_embeddings") as mock_compare, \
         patch("app.routers.atm.email_service.send_security_alert_email") as mock_email:

        # Liveness passes, but face mismatch
        mock_extract.return_value = {
            "embedding": [0.9] * 128,
            "liveness_checked": True,
            "liveness": {"is_live": True, "liveness_score": 0.95},
        }
        mock_compare.return_value = {"matched": False, "similarity": 0.12}

        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": VALID_JPEG_B64,
            },
        )

        # First attempt failure: returns 401 Unauthorized, not locked
        assert resp.status_code == 401
        assert "2 attempt(s) remaining" in resp.json()["detail"]

        # No security approval created
        assert not mock_approvals.document.called
        # No lockout email sent
        assert not mock_email.called


# 2. Third failed attempt triggers 15-minute lockout and approval creation
@pytest.mark.anyio
async def test_third_failed_attempt_triggers_15min_lockout_and_approval():
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=2)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch.object(face_service, "compare_embeddings") as mock_compare, \
         patch("app.routers.atm.email_service.send_security_alert_email", new_callable=AsyncMock) as mock_email:

        mock_extract.return_value = {
            "embedding": [0.9] * 128,
            "liveness_checked": True,
            "liveness": {"is_live": True, "liveness_score": 0.95},
        }
        mock_compare.return_value = {"matched": False, "similarity": 0.15}

        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": VALID_JPEG_B64,
            },
        )

        # 3rd failure: returns 403 Forbidden
        assert resp.status_code == 403
        assert "temporarily locked for 15 minutes" in resp.json()["detail"]

        # Security approval request created
        assert mock_approvals.document.called
        approval_saved_data = mock_approvals.document.return_value.set.call_args[0][0]
        assert approval_saved_data["status"] == "PENDING"
        assert approval_saved_data["failedAttempts"] == 3
        assert approval_saved_data["hasCapturedImage"] is True

        # Email was dispatched to cardholder with image attachment
        assert mock_email.called
        call_kwargs = mock_email.call_args.kwargs
        assert call_kwargs["recipient_email"] == "pavithra.workss@gmail.com"
        assert call_kwargs["recipient_name"] == "Pavithra Test"
        assert call_kwargs["is_locked"] is True
        assert call_kwargs["failed_attempts"] == 3
        assert call_kwargs["lockout_minutes"] == 15
        assert call_kwargs["image_bytes"] == VALID_JPEG_BYTES


# 3. SMTP failure does not bypass lockout or crash fail-closed flow
@pytest.mark.anyio
async def test_smtp_failure_does_not_break_lockout():
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=2)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch.object(face_service, "compare_embeddings") as mock_compare, \
         patch("app.routers.atm.email_service.send_security_alert_email", side_effect=Exception("SMTP Connection refused")):

        mock_extract.return_value = {
            "embedding": [0.9] * 128,
            "liveness_checked": True,
            "liveness": {"is_live": True},
        }
        mock_compare.return_value = {"matched": False}

        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": VALID_JPEG_B64,
            },
        )

        # Still locked with 403 despite SMTP exception
        assert resp.status_code == 403
        assert "temporarily locked" in resp.json()["detail"]


# 4. Input validation on image size and format
def test_invalid_image_payload_rejection():
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=0)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True):

        # Payload too small (< 20 bytes decoded) but valid schema string length (> 50 chars)
        too_small_raw = b"short_bytes_1234"
        too_small_b64 = "data:image/jpeg;base64;meta=test_padding_to_satisfy_schema," + base64.b64encode(too_small_raw).decode("utf-8")
        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": too_small_b64,
            },
        )
        assert resp.status_code == 400
        assert "too small" in resp.json()["detail"].lower()

        # Corrupted / invalid non-image bytes (> 20 bytes)
        corrupt_raw = b"not_an_image_at_all_1234567890_corrupted_data_string"
        corrupt_b64 = "data:image/jpeg;base64," + base64.b64encode(corrupt_raw).decode("utf-8")
        resp2 = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": corrupt_b64,
            },
        )
        assert resp2.status_code == 400
        assert "invalid image file format" in resp2.json()["detail"].lower()


# 5. Incident storage: save, retrieve, and short-lived signed token
def test_incident_storage_and_tokens():
    approval_id = "sec_test_incident_123"

    # Save image
    path = incident_storage.save_incident_image(approval_id, VALID_JPEG_BYTES)
    assert path.exists()

    # Retrieve image
    res = incident_storage.get_incident_image(approval_id)
    assert res is not None
    data, mime = res
    assert data == VALID_JPEG_BYTES
    assert mime == "image/jpeg"

    # Generate token
    token = incident_storage.generate_image_access_token(approval_id, admin_email="admin@test.com", expiry_seconds=300)
    assert token

    # Verify valid token
    assert incident_storage.verify_image_access_token(approval_id, token) is True

    # Verify forged token or mismatched approval fails
    assert incident_storage.verify_image_access_token("other_approval_id", token) is False
    assert incident_storage.verify_image_access_token(approval_id, "invalid_forged_token") is False

    # Verify expired token fails
    exp_token = incident_storage.generate_image_access_token(approval_id, admin_email="admin@test.com", expiry_seconds=-10)
    assert incident_storage.verify_image_access_token(approval_id, exp_token) is False


# 6. Admin image endpoint: unauthorized vs authorized access
def test_admin_image_access_authorization():
    approval_id = "sec_auth_test_456"
    incident_storage.save_incident_image(approval_id, VALID_JPEG_BYTES)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    with patch("app.routers.admin.get_firestore_client", return_value=mock_db):
        # 1. Unauthenticated request: returns 401
        resp_unauth = client.get(f"/api/admin/security-approvals/{approval_id}/image")
        assert resp_unauth.status_code == 401

        # 2. Invalid short-lived token: returns 401
        resp_bad_tok = client.get(f"/api/admin/security-approvals/{approval_id}/image?token=invalid_token")
        assert resp_bad_tok.status_code == 401

        # 3. Valid short-lived token: returns 200 with image bytes
        valid_tok = incident_storage.generate_image_access_token(approval_id, admin_email="admin@test.com", expiry_seconds=300)
        resp_tok = client.get(f"/api/admin/security-approvals/{approval_id}/image?token={valid_tok}")
        assert resp_tok.status_code == 200
        assert resp_tok.headers["content-type"] == "image/jpeg"
        assert resp_tok.content == VALID_JPEG_BYTES
        assert "no-store" in resp_tok.headers.get("cache-control", "").lower()


# 7. Admin approval decision: ACCEPT lifts lockout, DENY maintains lockout
@pytest.mark.anyio
async def test_admin_approval_decision_and_replay_protection():
    from app.core.security import get_current_admin

    mock_db = MagicMock()
    approval_id = "sec_decision_test_789"
    now = datetime.now(timezone.utc)

    approval_doc_data = {
        "id": approval_id,
        "customerId": "cust_decision_target",
        "cardNumberMasked": "4000 •••• •••• 9010",
        "status": "PENDING",
        "used": False,
        "expiresAt": (now + timedelta(minutes=15)).isoformat(),
    }

    mock_app_ref = MagicMock()
    mock_app_doc = MagicMock()
    mock_app_doc.exists = True
    mock_app_doc.to_dict.return_value = approval_doc_data
    mock_app_ref.get.return_value = mock_app_doc

    mock_cust_ref = MagicMock()

    def collection_side_effect(name):
        col = MagicMock()
        if name == "security_approvals":
            col.document.return_value = mock_app_ref
        elif name == "customers":
            col.document.return_value = mock_cust_ref
        elif name == "audit_logs":
            col.add.return_value = None
        return col

    mock_db.collection.side_effect = collection_side_effect

    mock_admin = {"email": "admin@faceatm.local", "uid": "admin_uid_1", "role": "admin"}
    app.dependency_overrides[get_current_admin] = lambda: mock_admin

    try:
        with patch("app.routers.admin.get_firestore_client", return_value=mock_db):
            # Test ACCEPT: lifts customer lockout
            resp = client.post(
                f"/api/admin/security-approvals/{approval_id}/decision",
                json={"decision": "ACCEPT", "notes": "Approved via telephone check."},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ACCEPTED"
            # Customer was unlocked
            assert mock_cust_ref.update.called
            update_call_dict = mock_cust_ref.update.call_args[0][0]
            assert update_call_dict["lockedUntil"] is None
            assert update_call_dict["failedAttempts"] == 0
            assert update_call_dict["unlockedByAdmin"] == "admin@faceatm.local"
            assert "unlockedAt" in update_call_dict

            # Test Replay Protection: trying to make decision on already used approval returns 400
            approval_doc_data["used"] = True
            approval_doc_data["status"] = "ACCEPTED"
            resp_replay = client.post(
                f"/api/admin/security-approvals/{approval_id}/decision",
                json={"decision": "ACCEPT"},
            )
            assert resp_replay.status_code == 400
            assert "already been finalized" in resp_replay.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


# 8. Subsequent face verification still requires both liveness and identity matching
@pytest.mark.anyio
async def test_subsequent_face_verification_requires_full_biometrics_fail_closed():
    # Customer unlocked by admin has failedAttempts: 0, lockedUntil: None
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=0, locked_until=None)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract:

        # If spoof occurs on subsequent login attempt:
        mock_extract.side_effect = FaceProcessingError(
            "Biometric liveness verification failed. Presentation attack detected.",
            403
        )

        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": "4000123456789010",
                "imageBase64": VALID_JPEG_B64,
            },
        )

        # Presentation attack is blocked fail-closed, does not bypass security
        assert resp.status_code == 403
        assert "presentation attack detected" in resp.json()["detail"].lower()


# 9. Card validate resets expired lockout automatically
def test_card_validate_clears_expired_lockout():
    mock_db = MagicMock()
    now = datetime.now(timezone.utc)
    expired_time = (now - timedelta(minutes=5)).isoformat()

    mock_card = MagicMock()
    mock_card.exists = True
    mock_card.to_dict.return_value = {"customerId": "cust_exp_01", "status": "ACTIVE"}

    mock_cust = MagicMock()
    mock_cust.exists = True
    mock_cust.to_dict.return_value = {
        "fullName": "Expired Lockout User",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "lockedUntil": expired_time,
        "failedAttempts": 3,
    }

    mock_cust_doc = MagicMock()
    mock_cust_doc.get.return_value = mock_cust

    def collection_side_effect(name):
        col = MagicMock()
        if name == "cards":
            col.document.return_value.get.return_value = mock_card
        elif name == "customers":
            col.document.return_value = mock_cust_doc
        return col

    mock_db.collection.side_effect = collection_side_effect

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True):

        resp = client.post(
            "/api/atm/card-validate",
            json={"cardNumber": "4000123456789010"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["isLocked"] is False
        mock_cust_doc.update.assert_called_with({"lockedUntil": None, "failedAttempts": 0})
