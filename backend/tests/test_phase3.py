"""Comprehensive automated test suite for Phase 3:
Customer Login, Face Biometric Verification, Simulated ATM Transactions, and Security Approvals.
"""

import sys
import os
import base64
import io
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.config import settings
from app.core.crypto import generate_unique_card_number, mask_card_number
from app.services.face_service import face_service, FaceProcessingError

client = TestClient(app)


def _create_synthetic_face_image_b64() -> str:
    """Generate a valid synthetic RGB image in base64 format."""
    img = Image.new("RGB", (200, 200), color=(220, 200, 180))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class MockFirestoreStore:
    """Reliable in-memory Firestore mockup for automated unit and integration tests."""

    def __init__(self):
        self.store = {}
        self.audit_logs = []

    def collection(self, col_name):
        return MockCollection(self, col_name)

    def transaction(self):
        t = MagicMock()
        t.update.side_effect = lambda doc_ref, data: doc_ref.update(data)
        t.set.side_effect = lambda doc_ref, data: doc_ref.set(data)
        return t


    def batch(self):
        b = MagicMock()
        b.commit.return_value = None
        return b


class MockCollection:
    def __init__(self, db: MockFirestoreStore, name: str):
        self.db = db
        self.name = name

    def document(self, doc_id: str):
        return MockDocumentRef(self.db, self.name, str(doc_id))

    def add(self, data: dict):
        self.db.audit_logs.append(data)
        doc = MagicMock()
        doc.id = f"auto_{len(self.db.audit_logs)}"
        return doc

    def stream(self):
        docs = []
        col_data = self.db.store.get(self.name, {})
        for k, v in col_data.items():
            doc = MagicMock()
            doc.id = k
            doc.to_dict.return_value = v.copy()
            doc.reference = MockDocumentRef(self.db, self.name, k)
            docs.append(doc)
        return docs

    def order_by(self, field, direction=None):
        return self

    def limit(self, n):
        return self


class MockDocumentRef:
    def __init__(self, db: MockFirestoreStore, col_name: str, doc_id: str):
        self.db = db
        self.col_name = col_name
        self.doc_id = doc_id

    def get(self, transaction=None):
        doc = MagicMock()
        col = self.db.store.get(self.col_name, {})
        if self.doc_id in col:
            doc.exists = True
            doc.id = self.doc_id
            doc.to_dict.return_value = col[self.doc_id].copy()
        else:
            doc.exists = False
            doc.id = self.doc_id
            doc.to_dict.return_value = None
        return doc

    def set(self, data: dict):
        if self.col_name not in self.db.store:
            self.db.store[self.col_name] = {}
        self.db.store[self.col_name][self.doc_id] = data.copy()

    def update(self, data: dict):
        if self.col_name not in self.db.store:
            self.db.store[self.col_name] = {}
        if self.doc_id not in self.db.store[self.col_name]:
            self.db.store[self.col_name][self.doc_id] = {}
        self.db.store[self.col_name][self.doc_id].update(data)

    def collection(self, sub_name: str):
        full_name = f"{self.col_name}/{self.doc_id}/{sub_name}"
        return MockCollection(self.db, full_name)


@pytest.fixture
def in_memory_db():
    """Provide an in-memory database patched across routers and security dependencies."""
    db = MockFirestoreStore()
    with patch("app.routers.atm.get_firestore_client", return_value=db), \
         patch("app.core.security.get_firestore_client", return_value=db), \
         patch("app.routers.admin.get_firestore_client", return_value=db):
        yield db


def test_face_service_compare_embeddings():
    """Test 128-dimensional embedding comparison using cosine similarity."""
    v1 = [0.1] * 128
    v1_norm = [float(x / np.linalg.norm(v1)) for x in v1]
    res_identical = face_service.compare_embeddings(v1_norm, v1_norm, threshold=0.40)
    assert res_identical["matched"] is True
    assert pytest.approx(res_identical["similarity"], 0.001) == 1.0

    v_a = [1.0] + [0.0] * 127
    v_b = [0.0, 1.0] + [0.0] * 126
    res_orthogonal = face_service.compare_embeddings(v_a, v_b, threshold=0.40)
    assert res_orthogonal["matched"] is False
    assert pytest.approx(res_orthogonal["similarity"], 0.001) == 0.0

    with pytest.raises(FaceProcessingError):
        face_service.compare_embeddings([0.1] * 64, [0.1] * 128)


def test_card_validation_invalid_luhn(in_memory_db):
    """Test that invalid Luhn card numbers are rejected with 400 Bad Request."""
    # 1234567812345671 fails Luhn check
    resp = client.post("/api/atm/card-validate", json={"cardNumber": "1234567812345671"})
    assert resp.status_code == 400
    assert "Invalid card number checksum" in resp.json()["detail"]


def test_card_validation_not_found(in_memory_db):
    """Test valid Luhn format but non-existent card in database."""
    card = generate_unique_card_number()
    resp = client.post("/api/atm/card-validate", json={"cardNumber": card})
    assert resp.status_code == 404
    assert "Card not found" in resp.json()["detail"]


def test_card_validation_success_and_lockout(in_memory_db):
    """Test card validation for active card and lockout detection."""
    card = generate_unique_card_number()
    cust_id = "cust_test_123"

    in_memory_db.collection("cards").document(card).set({
        "cardNumber": card,
        "customerId": cust_id,
        "status": "ACTIVE",
    })

    in_memory_db.collection("customers").document(cust_id).set({
        "id": cust_id,
        "fullName": "Jane Doe",
        "cardNumber": card,
        "cardNumberMasked": mask_card_number(card),
        "status": "ACTIVE",
        "faceEnrolled": True,
        "lockedUntil": None,
    })

    # Active card validation
    resp = client.post("/api/atm/card-validate", json={"cardNumber": card})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["isLocked"] is False
    assert data["fullName"] == "Jane Doe"

    # Now simulate active lockout
    locked_until = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    in_memory_db.collection("customers").document(cust_id).update({
        "lockedUntil": locked_until,
    })

    resp_locked = client.post("/api/atm/card-validate", json={"cardNumber": card})
    assert resp_locked.status_code == 200
    locked_data = resp_locked.json()
    assert locked_data["valid"] is False
    assert locked_data["isLocked"] is True
    assert locked_data["lockoutRemainingSeconds"] > 0


def test_face_login_success(in_memory_db):
    """Test successful face verification flow issuing customer session."""
    card = generate_unique_card_number()
    cust_id = "cust_test_success"
    enrolled_embedding = [0.05] * 128
    enrolled_norm = [float(x / np.linalg.norm(enrolled_embedding)) for x in enrolled_embedding]

    in_memory_db.collection("cards").document(card).set({
        "cardNumber": card,
        "customerId": cust_id,
        "status": "ACTIVE",
    })

    in_memory_db.collection("customers").document(cust_id).set({
        "id": cust_id,
        "fullName": "Alice Smith",
        "email": "alice@example.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "lockedUntil": None,
        "failedAttempts": 0,
        "balance": 25000.0,
    })

    in_memory_db.collection("customers").document(cust_id).collection("biometrics").document("face").set({
        "embedding": enrolled_norm,
    })

    # Mock face_service processing and comparison
    with patch.object(face_service, "process_and_extract_embedding") as mock_extract:
        mock_extract.return_value = {"embedding": enrolled_norm}
        with patch.object(face_service, "compare_embeddings") as mock_compare:
            mock_compare.return_value = {"matched": True, "similarity": 0.95, "threshold": 0.40}

            img_b64 = _create_synthetic_face_image_b64()
            resp = client.post("/api/atm/login-face", json={"cardNumber": card, "imageBase64": img_b64})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["sessionToken"].startswith("cust_sess_")
            assert data["customerId"] == cust_id
            assert data["fullName"] == "Alice Smith"
            assert data["balance"] == 25000.0


def test_face_login_mismatch_and_lockout_trigger(in_memory_db):
    """Test that failed face match increments failedAttempts and triggers lockout on 3rd failure."""
    card = generate_unique_card_number()
    cust_id = "cust_test_fail"
    enrolled_embedding = [0.05] * 128

    in_memory_db.collection("cards").document(card).set({
        "cardNumber": card,
        "customerId": cust_id,
        "status": "ACTIVE",
    })

    in_memory_db.collection("customers").document(cust_id).set({
        "id": cust_id,
        "fullName": "Bob Ross",
        "email": "bob@example.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "lockedUntil": None,
        "failedAttempts": 2,  # 3rd will trigger lockout
        "balance": 25000.0,
    })

    in_memory_db.collection("customers").document(cust_id).collection("biometrics").document("face").set({
        "embedding": enrolled_embedding,
    })

    with patch.object(face_service, "process_and_extract_embedding") as mock_extract:
        mock_extract.return_value = {"embedding": [0.0] * 128}
        with patch.object(face_service, "compare_embeddings") as mock_compare:
            mock_compare.return_value = {"matched": False, "similarity": 0.12, "threshold": 0.40}
            with patch("app.services.email_service.email_service.send_security_alert_email") as mock_email:
                mock_email.return_value = {"delivered": True}

                img_b64 = _create_synthetic_face_image_b64()
                resp = client.post("/api/atm/login-face", json={"cardNumber": card, "imageBase64": img_b64})
                # Lockout is triggered -> 403 Forbidden
                assert resp.status_code == 403
                assert "temporarily locked" in resp.json()["detail"]

                # Ensure customer record has lockedUntil set
                cust_data = in_memory_db.collection("customers").document(cust_id).get().to_dict()
                assert cust_data["lockedUntil"] is not None
                assert cust_data["failedAttempts"] == 3

                # Ensure security approval request created in Firestore
                approvals = in_memory_db.collection("security_approvals").stream()
                assert len(approvals) == 1
                assert approvals[0].to_dict()["customerId"] == cust_id


def test_customer_session_authentication_and_isolation(in_memory_db):
    """Test customer authenticated endpoints and isolation."""
    session_token = "cust_sess_valid_token_123"
    cust_id = "cust_authenticated_user"

    in_memory_db.collection("customer_sessions").document(session_token).set({
        "sessionId": session_token,
        "customerId": cust_id,
        "fullName": "Charlie Brown",
        "cardNumberMasked": "XXXX-XXXX-XXXX-9999",
        "active": True,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    })

    in_memory_db.collection("customers").document(cust_id).set({
        "id": cust_id,
        "fullName": "Charlie Brown",
        "cardNumberMasked": "XXXX-XXXX-XXXX-9999",
        "status": "ACTIVE",
        "bankName": "Face ATM Bank",
        "balance": 25000.0,
    })

    # 1. Unauthenticated request -> 401
    resp_unauth = client.get("/api/atm/balance")
    assert resp_unauth.status_code == 401

    # 2. Authenticated balance check
    headers = {"Authorization": f"Bearer {session_token}"}
    resp_auth = client.get("/api/atm/balance", headers=headers)
    assert resp_auth.status_code == 200
    bal_data = resp_auth.json()
    assert bal_data["customerId"] == cust_id
    assert bal_data["balance"] == 25000.0
    assert bal_data["isSimulated"] is True

    # 3. Customer Dashboard
    resp_dash = client.get("/api/atm/dashboard", headers=headers)
    assert resp_dash.status_code == 200
    dash_data = resp_dash.json()
    assert dash_data["customerId"] == cust_id
    assert dash_data["balance"] == 25000.0

    # 4. Logout
    resp_logout = client.post("/api/atm/logout", headers=headers)
    assert resp_logout.status_code == 200
    assert resp_logout.json()["success"] is True

    # After logout, accessing balance should fail
    resp_after = client.get("/api/atm/balance", headers=headers)
    assert resp_after.status_code == 401


def test_simulated_transactions_validation_and_concurrency(in_memory_db):
    """Test simulated withdrawal and deposit validation and limits."""
    session_token = "cust_sess_txn_token"
    cust_id = "cust_txn_user"

    in_memory_db.collection("customer_sessions").document(session_token).set({
        "sessionId": session_token,
        "customerId": cust_id,
        "fullName": "Diana Prince",
        "active": True,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    })

    in_memory_db.collection("customers").document(cust_id).set({
        "id": cust_id,
        "fullName": "Diana Prince",
        "status": "ACTIVE",
        "balance": 5000.0,
    })

    headers = {"Authorization": f"Bearer {session_token}"}

    # 1. Invalid withdrawal amount (not divisible by 100)
    resp_invalid = client.post("/api/atm/withdraw", json={"amount": 250}, headers=headers)
    assert resp_invalid.status_code == 422  # Pydantic validation error

    # 2. Exceeds max transaction limit of 20,000
    resp_overlimit = client.post("/api/atm/withdraw", json={"amount": 25000}, headers=headers)
    assert resp_overlimit.status_code == 422

    # 3. Insufficient balance (balance is 5000, requesting 6000)
    resp_insufficient = client.post("/api/atm/withdraw", json={"amount": 6000.0}, headers=headers)
    assert resp_insufficient.status_code == 400
    assert "Insufficient funds" in resp_insufficient.json()["detail"]

    # 4. Successful withdrawal of 2000
    resp_withdraw = client.post("/api/atm/withdraw", json={"amount": 2000.0}, headers=headers)
    assert resp_withdraw.status_code == 200
    w_data = resp_withdraw.json()
    assert w_data["success"] is True
    assert w_data["amount"] == 2000.0
    assert w_data["previousBalance"] == 5000.0
    assert w_data["newBalance"] == 3000.0

    # 5. Successful deposit of 1500
    resp_deposit = client.post("/api/atm/deposit", json={"amount": 1500.0}, headers=headers)
    assert resp_deposit.status_code == 200
    d_data = resp_deposit.json()
    assert d_data["success"] is True
    assert d_data["amount"] == 1500.0
    assert d_data["previousBalance"] == 3000.0
    assert d_data["newBalance"] == 4500.0


def test_admin_security_approvals_lifecycle(in_memory_db):
    """Test admin security approval list and Accept/Deny decision flow."""
    admin_headers = {"Authorization": "Bearer admin_token_valid"}

    # Mock admin authentication
    with patch("app.core.security.verify_firebase_token") as mock_verify:
        mock_verify.return_value = {
            "uid": "admin_uid_123",
            "email": settings.ADMIN_EMAIL,
            "admin": True,
        }

        # Seed customer and locked approval
        cust_id = "cust_locked_user"
        in_memory_db.collection("customers").document(cust_id).set({
            "id": cust_id,
            "fullName": "Locked User",
            "status": "ACTIVE",
            "lockedUntil": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "failedAttempts": 3,
        })

        in_memory_db.collection("security_approvals").document("sec_test_appr").set({
            "id": "sec_test_appr",
            "customerId": cust_id,
            "customerName": "Locked User",
            "customerEmail": "locked@example.com",
            "cardNumberMasked": "XXXX-XXXX-XXXX-1111",
            "reason": "Exceeded failed verification attempts",
            "failedAttempts": 3,
            "status": "PENDING",
            "used": False,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        })

        # 1. List security approvals
        resp_list = client.get("/api/admin/security-approvals", headers=admin_headers)
        assert resp_list.status_code == 200
        assert resp_list.json()["count"] == 1
        assert resp_list.json()["approvals"][0]["id"] == "sec_test_appr"

        # 2. Accept decision
        resp_accept = client.post(
            "/api/admin/security-approvals/sec_test_appr/decision",
            json={"decision": "ACCEPT", "notes": "Identity confirmed via phone"},
            headers=admin_headers,
        )
        assert resp_accept.status_code == 200
        assert resp_accept.json()["status"] == "ACCEPTED"

        # Ensure customer lockout was reset
        cust_data = in_memory_db.collection("customers").document(cust_id).get().to_dict()
        assert cust_data["lockedUntil"] is None
        assert cust_data["failedAttempts"] == 0

        # 3. Reject reuse of already finalized request
        resp_reused = client.post(
            "/api/admin/security-approvals/sec_test_appr/decision",
            json={"decision": "DENY"},
            headers=admin_headers,
        )
        assert resp_reused.status_code == 400
        assert "already been finalized" in resp_reused.json()["detail"]
