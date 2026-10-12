"""Automated verification tests for:
1. Card Owner Security Alert (Mismatched face image sent to real card owner with ACCEPT / DENY options).
2. Live face recognition feedback ('Face Not Recognizable — Please show your full face to the camera').
3. Strict biometric integrity: ACCEPT lifts lockout for retry, but never bypasses face matching.
"""

import sys
import os
import base64
import io
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from PIL import Image
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


def _create_blank_image_b64() -> str:
    """Create a blank black 320x320 image."""
    img = Image.new("RGB", (320, 320), color="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def mock_customer_db(failed_attempts=0, locked_until=None):
    """Create mock Firestore DB with a registered active card and customer."""
    mock_db = MagicMock()
    card_number = "4000123456789010"

    mock_card = MagicMock()
    mock_card.exists = True
    mock_card.to_dict.return_value = {
        "customerId": "cust_test_owner_flow",
        "cardNumber": card_number,
        "status": "ACTIVE",
    }

    cust_data = {
        "fullName": "Pavithra CardOwner",
        "email": "owner.registered@example.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "failedAttempts": failed_attempts,
        "lockedUntil": locked_until,
        "balance": 25000.0,
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


# =========================================================================
# Feature 2: Face Not Recognizable When Face is Hidden / Covered / Obscured
# =========================================================================

def test_live_face_check_endpoint_hidden_face():
    """Verify POST /api/atm/face-check returns recognizable: False and clear prompt when face is obscured."""
    blank_b64 = _create_blank_image_b64()

    resp = client.post("/api/atm/face-check", json={"imageBase64": blank_b64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["recognizable"] is False
    assert "Face Not Recognizable — Please show your full face to the camera." in data["message"]


def test_live_face_check_endpoint_visible_face():
    """Verify POST /api/atm/face-check returns recognizable: True when face is clearly detected."""
    with patch.object(face_service, "detect_face_presence") as mock_detect:
        mock_detect.return_value = {
            "recognizable": True,
            "confidence": 0.94,
            "message": "Face detected — Please look directly at the camera.",
        }

        resp = client.post("/api/atm/face-check", json={"imageBase64": VALID_JPEG_B64})
        assert resp.status_code == 200
        data = resp.json()
        assert data["recognizable"] is True
        assert data["confidence"] == 0.94


@pytest.mark.anyio
async def test_hidden_face_in_login_returns_400_and_does_not_increment_failed_attempts():
    """Hiding or covering face during login attempt must NOT increment failed attempts or lock card."""
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=1)
    blank_b64 = _create_blank_image_b64()

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract:

        mock_extract.side_effect = FaceProcessingError(
            "Face Not Recognizable — Please show your full face to the camera. No face detected in the captured image.",
            400,
        )

        resp = client.post(
            "/api/atm/login-face",
            json={"cardNumber": "4000123456789010", "imageBase64": blank_b64},
        )

        # Returns 400 Bad Request
        assert resp.status_code == 400
        assert "Face Not Recognizable — Please show your full face to the camera." in resp.json()["detail"]

        # Ensure failedAttempts was NOT incremented on customer record
        assert not mock_cust_doc.update.called
        # Ensure no security approval or lockout email was created
        assert not mock_approvals.document.called


# =========================================================================
# Feature 1: Send Last Failed Face Image to Real Card Owner (ACCEPT / DENY)
# =========================================================================

@pytest.mark.anyio
async def test_failed_face_mismatch_sends_email_to_registered_owner_with_image_and_tokens():
    """On third failed face attempt (lockout), stores latest failed image, creates approval, and dispatches email."""
    mock_db, mock_cust_doc, mock_approvals, cust_data = mock_customer_db(failed_attempts=2)

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch.object(face_service, "compare_embeddings") as mock_compare, \
         patch("app.routers.atm.email_service.send_security_alert_email", new_callable=AsyncMock) as mock_email:

        mock_extract.return_value = {
            "embedding": [0.8] * 128,
            "liveness_checked": True,
            "liveness": {"is_live": True},
        }
        mock_compare.return_value = {"matched": False, "similarity": 0.15}

        resp = client.post(
            "/api/atm/login-face",
            json={"cardNumber": "4000123456789010", "imageBase64": VALID_JPEG_B64},
        )

        assert resp.status_code == 403
        assert "temporarily locked" in resp.json()["detail"]

        # Email sent to real registered card owner, NEVER an unauthenticated email
        assert mock_email.called
        call_kwargs = mock_email.call_args.kwargs
        assert call_kwargs["recipient_email"] == "owner.registered@example.com"
        assert call_kwargs["recipient_name"] == "Pavithra CardOwner"
        assert call_kwargs["image_bytes"] == VALID_JPEG_BYTES
        assert call_kwargs["approval_id"] is not None
        assert call_kwargs["accept_token"] is not None
        assert call_kwargs["deny_token"] is not None


def test_card_owner_incident_details_endpoint_security():
    """Verify GET /api/atm/security-alert/{incident_id} requires signed HMAC token and protects PII."""
    incident_id = "sec_owner_test_101"
    customer_id = "cust_test_owner_flow"

    valid_token = incident_storage.generate_owner_decision_token(
        approval_id=incident_id,
        customer_id=customer_id,
        action="ACCEPT",
        expiry_seconds=300,
    )

    mock_db = MagicMock()
    mock_app_doc = MagicMock()
    mock_app_doc.exists = True
    mock_app_doc.to_dict.return_value = {
        "id": incident_id,
        "customerId": customer_id,
        "customerName": "Pavithra CardOwner",
        "customerEmail": "owner.registered@example.com",
        "cardNumberMasked": "4000 •••• •••• 9010",
        "status": "PENDING",
        "used": False,
        "hasCapturedImage": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_app_doc

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db):
        # 1. Unauthenticated / missing token: 422 or 401
        res_no_token = client.get(f"/api/atm/security-alert/{incident_id}")
        assert res_no_token.status_code in (401, 422)

        # 2. Forged / invalid token: 401
        res_bad_token = client.get(f"/api/atm/security-alert/{incident_id}?token=bad_forged_token")
        assert res_bad_token.status_code == 401

        # 3. Valid token: 200 with masked card data (email is stripped)
        res_ok = client.get(f"/api/atm/security-alert/{incident_id}?token={valid_token}")
        assert res_ok.status_code == 200
        data = res_ok.json()
        assert data["incidentId"] == incident_id
        assert data["cardNumberMasked"] == "4000 •••• •••• 9010"
        assert data["hasCapturedImage"] is True
        assert data["status"] == "PENDING"
        assert "owner.registered@example.com" not in str(data)  # PII not leaked


@pytest.mark.anyio
async def test_card_owner_accept_decision_lifts_lockout_and_enforces_replay_protection():
    """Owner ACCEPT clears lockout so customer can retry, but records audit and blocks replay."""
    incident_id = "sec_owner_accept_202"
    customer_id = "cust_test_owner_flow"

    accept_token = incident_storage.generate_owner_decision_token(
        approval_id=incident_id,
        customer_id=customer_id,
        action="ACCEPT",
        expiry_seconds=300,
    )

    mock_db = MagicMock()
    approval_data = {
        "id": incident_id,
        "customerId": customer_id,
        "cardNumberMasked": "4000 •••• •••• 9010",
        "status": "PENDING",
        "used": False,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }
    mock_app_ref = MagicMock()
    mock_app_doc = MagicMock()
    mock_app_doc.exists = True
    mock_app_doc.to_dict.return_value = approval_data
    mock_app_ref.get.return_value = mock_app_doc

    mock_cust_ref = MagicMock()

    def col_side_effect(name):
        col = MagicMock()
        if name == "security_approvals":
            col.document.return_value = mock_app_ref
        elif name == "customers":
            col.document.return_value = mock_cust_ref
        elif name == "audit_logs":
            col.add.return_value = None
        return col

    mock_db.collection.side_effect = col_side_effect

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db):
        resp = client.post(
            f"/api/atm/security-alert/{incident_id}/decision",
            json={"decision": "ACCEPT", "token": accept_token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACCEPTED"

        # Customer lockout lifted
        assert mock_cust_ref.update.called
        update_args = mock_cust_ref.update.call_args[0][0]
        assert update_args["lockedUntil"] is None
        assert update_args["failedAttempts"] == 0
        assert update_args["unlockedByOwner"] is True

        # Replay protection: cannot accept or deny again
        approval_data["used"] = True
        approval_data["status"] = "ACCEPTED"
        resp_replay = client.post(
            f"/api/atm/security-alert/{incident_id}/decision",
            json={"decision": "ACCEPT", "token": accept_token},
        )
        assert resp_replay.status_code == 400
        assert "already been finalized" in resp_replay.json()["detail"].lower()


@pytest.mark.anyio
async def test_card_owner_deny_decision_maintains_lockout():
    """Owner DENY maintains security lockout and denies access."""
    incident_id = "sec_owner_deny_303"
    customer_id = "cust_test_owner_flow"

    deny_token = incident_storage.generate_owner_decision_token(
        approval_id=incident_id,
        customer_id=customer_id,
        action="DENY",
        expiry_seconds=300,
    )

    mock_db = MagicMock()
    approval_data = {
        "id": incident_id,
        "customerId": customer_id,
        "cardNumberMasked": "4000 •••• •••• 9010",
        "status": "PENDING",
        "used": False,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }
    mock_app_ref = MagicMock()
    mock_app_doc = MagicMock()
    mock_app_doc.exists = True
    mock_app_doc.to_dict.return_value = approval_data
    mock_app_ref.get.return_value = mock_app_doc

    mock_cust_ref = MagicMock()

    def col_side_effect(name):
        col = MagicMock()
        if name == "security_approvals":
            col.document.return_value = mock_app_ref
        elif name == "customers":
            col.document.return_value = mock_cust_ref
        elif name == "audit_logs":
            col.add.return_value = None
        return col

    mock_db.collection.side_effect = col_side_effect

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db):
        resp = client.post(
            f"/api/atm/security-alert/{incident_id}/decision",
            json={"decision": "DENY", "token": deny_token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DENIED"

        # Customer lockout was NOT lifted
        assert not mock_cust_ref.update.called
        # Incident marked DENIED and used
        mock_app_ref.update.assert_called_with({
            "status": "DENIED",
            "used": True,
            "decision": "DENY",
            "decidedBy": "CARD_OWNER",
            "decidedAt": mock_app_ref.update.call_args[0][0]["decidedAt"],
        })


def test_card_owner_html_decision_link_browser_support():
    """Verify GET /api/atm/security-alert/{incident_id}/decision serves responsive HTML page."""
    incident_id = "sec_html_test_404"
    customer_id = "cust_test_owner_flow"

    token = incident_storage.generate_owner_decision_token(
        approval_id=incident_id,
        customer_id=customer_id,
        action="ACCEPT",
        expiry_seconds=300,
    )

    mock_db = MagicMock()
    approval_data = {
        "id": incident_id,
        "customerId": customer_id,
        "cardNumberMasked": "4000 •••• •••• 9010",
        "status": "PENDING",
        "used": False,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }
    mock_app_ref = MagicMock()
    mock_app_doc = MagicMock()
    mock_app_doc.exists = True
    mock_app_doc.to_dict.return_value = approval_data
    mock_app_ref.get.return_value = mock_app_doc

    mock_cust_ref = MagicMock()

    def col_side_effect(name):
        col = MagicMock()
        if name == "security_approvals":
            col.document.return_value = mock_app_ref
        elif name == "customers":
            col.document.return_value = mock_cust_ref
        elif name == "audit_logs":
            col.add.return_value = None
        return col

    mock_db.collection.side_effect = col_side_effect

    with patch("app.routers.atm.get_firestore_client", return_value=mock_db):
        resp = client.get(f"/api/atm/security-alert/{incident_id}/decision?token={token}&decision=ACCEPT")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Authorization Accepted" in resp.text
