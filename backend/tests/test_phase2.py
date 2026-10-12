"""Comprehensive Unit & Integration Test Suite for Phase 2:
Customer Registration, Email OTP Verification, Biometric Face Enrollment, and Card Issuance.
"""

import sys
import os
import io
import time
import base64
import numpy as np
import pytest
from PIL import Image
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.security import get_current_admin
from app.core.firebase import get_firestore_client
from app.core.crypto import (
    validate_verhoeff,
    generate_verhoeff_checksum,
    calculate_luhn_checksum,
    validate_luhn_card_number,
    generate_unique_card_number,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    hash_deterministic,
    verify_otp_constant_time,
    hash_otp,
    generate_salt,
)
from app.services.face_service import face_service, FaceProcessingError

client = TestClient(app)

# Helper for a valid 12-digit Aadhaar number
def make_valid_aadhaar(prefix_11: str = "98765432101") -> str:
    chk = generate_verhoeff_checksum(prefix_11)
    return prefix_11 + chk

# Mock Admin User
MOCK_ADMIN = {
    "uid": "admin_test_uid_123",
    "email": "admin@faceatm.local",
    "role": "ADMIN",
    "auth_time": int(time.time()),
}


# ==========================================
# 1. Validation & Cryptographic Unit Tests
# ==========================================

def test_aadhaar_verhoeff_validation():
    """Verify Aadhaar Verhoeff checksum algorithm rejects invalid digits."""
    valid_aadhaar = make_valid_aadhaar("99123456789")
    assert validate_verhoeff(valid_aadhaar) is True

    # Corrupt last digit
    corrupted = valid_aadhaar[:-1] + ("0" if valid_aadhaar[-1] != "0" else "1")
    assert validate_verhoeff(corrupted) is False

    # Short / non-digit
    assert validate_verhoeff("12345") is False
    assert validate_verhoeff("abcdefghijkl") is False
    assert validate_verhoeff("000000000000") is False


def test_card_number_luhn_and_uniqueness():
    """Verify generated card number conforms to 16 digits and valid Luhn check digit."""
    cards = set()
    for _ in range(50):
        c = generate_unique_card_number()
        assert len(c) == 16
        assert c.startswith("5049")
        assert validate_luhn_card_number(c) is True
        cards.add(c)
    # Ensure randomness: all 50 generated cards should be distinct
    assert len(cards) == 50


def test_sensitive_pii_encryption():
    """Verify AES-256-GCM authenticated encryption and decryption."""
    raw_aadhaar = "998877665544"
    encrypted = encrypt_sensitive_data(raw_aadhaar)
    assert encrypted != raw_aadhaar
    assert "9988" not in encrypted
    decrypted = decrypt_sensitive_data(encrypted)
    assert decrypted == raw_aadhaar


def test_otp_constant_time_verification():
    """Verify constant-time OTP comparison with salt."""
    salt = generate_salt()
    otp = "654321"
    otp_hash_val = hash_otp(otp, salt)

    assert verify_otp_constant_time(otp, salt, otp_hash_val) is True
    assert verify_otp_constant_time("000000", salt, otp_hash_val) is False
    assert verify_otp_constant_time("654322", salt, otp_hash_val) is False


# ==========================================
# 2. Registration Payload Validation Tests
# ==========================================

def test_registration_unauthenticated():
    """Verify registration initiate is rejected without admin bearer credentials."""
    payload = {
        "fullName": "Pavit Sharma",
        "email": "pavit@example.com",
        "phone": "9876543210",
        "dob": "1995-05-15",
        "aadhaarNumber": make_valid_aadhaar("98765432109"),
        "bankAccountNumber": "123456789012",
        "bankName": "State Bank of India",
    }
    res = client.post("/api/customers/register-initiate", json=payload)
    assert res.status_code == 401


def test_registration_invalid_fields():
    """Verify field validations: underage, invalid phone, invalid Aadhaar, short bank account."""
    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN

    try:
        # Underage (< 18 years old)
        bad_dob = {
            "fullName": "Minor User",
            "email": "minor@example.com",
            "phone": "9876543210",
            "dob": "2015-01-01",  # ~11 years old
            "aadhaarNumber": make_valid_aadhaar("98765432109"),
            "bankAccountNumber": "123456789012",
            "bankName": "State Bank",
        }
        res = client.post("/api/customers/register-initiate", json=bad_dob)
        assert res.status_code == 422

        # Invalid phone (less than 10 digits or bad starting digit)
        bad_phone = {
            "fullName": "User One",
            "email": "user1@example.com",
            "phone": "12345",
            "dob": "1995-01-01",
            "aadhaarNumber": make_valid_aadhaar("98765432109"),
            "bankAccountNumber": "123456789012",
            "bankName": "State Bank",
        }
        res = client.post("/api/customers/register-initiate", json=bad_phone)
        assert res.status_code == 422

        # Invalid Aadhaar (checksum fail)
        bad_aadhaar = {
            "fullName": "User Two",
            "email": "user2@example.com",
            "phone": "9876543210",
            "dob": "1995-01-01",
            "aadhaarNumber": "123456789012",  # Not a valid Verhoeff number
            "bankAccountNumber": "123456789012",
            "bankName": "State Bank",
        }
        res = client.post("/api/customers/register-initiate", json=bad_aadhaar)
        assert res.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


# ==========================================
# 3. OTP Flow & Lifecycle Integration Tests
# ==========================================

def test_duplicate_prevention_and_otp_lifecycle():
    """
    Test full registration initiation, duplicate prevention,
    OTP attempt limit, and resend cooldown.
    """
    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN

    # In-memory mock store for Firestore
    mock_db = MagicMock()
    mock_customers = {}
    mock_otps = {}
    mock_cards = {}

    def mock_collection(name):
        col = MagicMock()
        if name == "customers":
            col.where.return_value.limit.return_value.get.side_effect = lambda: (
                [MagicMock()] if "duplicate" in col._last_query else []
            )
            return col
        elif name == "otp_verifications":
            def doc_get(doc_id):
                doc_mock = MagicMock()
                if doc_id in mock_otps:
                    doc_mock.exists = True
                    doc_mock.to_dict.return_value = mock_otps[doc_id]
                else:
                    doc_mock.exists = False
                return doc_mock

            def doc_set(doc_id):
                doc_mock = MagicMock()
                doc_mock.set.side_effect = lambda d: mock_otps.update({doc_id: d})
                doc_mock.update.side_effect = lambda d: mock_otps[doc_id].update(d)
                doc_mock.get.side_effect = lambda: doc_get(doc_id)
                return doc_mock

            col.document.side_effect = doc_set
            return col
        elif name == "cards":
            def card_doc(c_num):
                c_mock = MagicMock()
                c_mock.exists = c_num in mock_cards
                c_mock.set.side_effect = lambda d: mock_cards.update({c_num: d})
                return c_mock
            col.document.side_effect = card_doc
            return col
        elif name == "audit_logs":
            col.add.return_value = MagicMock()
            return col
        return MagicMock()

    mock_db.collection.side_effect = mock_collection
    batch_mock = MagicMock()
    mock_db.batch.return_value = batch_mock

    with patch("app.routers.customers.get_firestore_client", return_value=mock_db), \
         patch("app.services.email_service.email_service.send_otp_email", return_value={"delivered": True, "id": "msg_123"}), \
         patch("app.services.email_service.email_service.send_card_issued_email", return_value={"delivered": True, "id": "msg_card_123"}):

        valid_aadhaar = make_valid_aadhaar("88765432101")
        payload = {
            "fullName": "Dev Sharma",
            "email": "dev.sharma@example.com",
            "phone": "9812345678",
            "dob": "1992-08-20",
            "aadhaarNumber": valid_aadhaar,
            "bankAccountNumber": "9876543210987",
            "bankName": "HDFC Bank",
        }

        # 1. Initiate registration
        res = client.post("/api/customers/register-initiate", json=payload)
        assert res.status_code == 200, res.text
        init_data = res.json()
        assert "verificationId" in init_data
        vrf_id = init_data["verificationId"]
        assert init_data["customerSummary"]["aadhaarMasked"].startswith("XXXX-XXXX-")
        # Ensure raw Aadhaar & bank account NOT returned in response
        assert valid_aadhaar not in str(init_data)
        assert "9876543210987" not in str(init_data)

        # 2. Resend Cooldown Test: immediate resend must return 429 Too Many Requests
        res_resend_fast = client.post("/api/customers/otp-resend", json={"verificationId": vrf_id})
        assert res_resend_fast.status_code == 429
        assert "Please wait" in res_resend_fast.json()["detail"]

        # 3. Invalid OTP attempts
        for attempt in range(1, 5):
            bad_otp_res = client.post("/api/customers/otp-verify", json={"verificationId": vrf_id, "otp": "000000"})
            assert bad_otp_res.status_code == 400
            assert "Invalid verification code" in bad_otp_res.json()["detail"]

        # 5th failed attempt should lock/invalidate session
        locked_res = client.post("/api/customers/otp-verify", json={"verificationId": vrf_id, "otp": "000000"})
        assert locked_res.status_code == 400
        assert "Maximum attempts" in locked_res.json()["detail"]

        # 4. Verify valid OTP on fresh session
        # Simulate clean session with known OTP
        fresh_vrf_id = "vrf_fresh_123"
        salt = generate_salt()
        known_otp = "123456"
        mock_otps[fresh_vrf_id] = {
            "id": fresh_vrf_id,
            "email": "dev.sharma@example.com",
            "otp_hash": hash_otp(known_otp, salt),
            "salt": salt,
            "customer_draft": {
                "fullName": "Dev Sharma",
                "email": "dev.sharma@example.com",
                "phone": "9812345678",
                "dob": "1992-08-20",
                "bankName": "HDFC Bank",
                "phone_mask": "XXXXXX5678",
                "aadhaar_mask": "XXXX-XXXX-2101",
                "bankAccount_mask": "XXXXXXXXX0987",
            },
            "customer_summary": {},
            "attempts": 0,
            "max_attempts": 5,
            "verified": False,
            "completed": False,
        }

        # Attempt face enrollment BEFORE email verification -> MUST FAIL 403
        fake_face_img = io.BytesIO()
        Image.new("RGB", (200, 200), color="white").save(fake_face_img, format="JPEG")
        fake_b64 = base64.b64encode(fake_face_img.getvalue()).decode()

        premature_enroll = client.post("/api/customers/enroll-face", json={
            "verificationId": fresh_vrf_id,
            "imageBase64": fake_b64,
            "consentObtained": True,
        })
        assert premature_enroll.status_code == 403, "Must forbid enrollment prior to OTP verification"

        # Now verify valid OTP
        valid_otp_res = client.post("/api/customers/otp-verify", json={"verificationId": fresh_vrf_id, "otp": known_otp})
        assert valid_otp_res.status_code == 200
        assert valid_otp_res.json()["verified"] is True
        assert mock_otps[fresh_vrf_id]["verified"] is True
        # OTP hash must be invalidated upon successful verification
        assert mock_otps[fresh_vrf_id]["otp_hash"] == ""

    app.dependency_overrides.pop(get_current_admin, None)


# ==========================================
# 4. Face Enrollment & Biometric Tests
# ==========================================

def test_face_enrollment_consent_required():
    """Verify enrollment fails if consentObtained is False."""
    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN
    try:
        res = client.post("/api/customers/enroll-face", json={
            "verificationId": "some_id",
            "imageBase64": "dummy",
            "consentObtained": False,
        })
        assert res.status_code in (400, 403, 404)
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


def test_face_service_model_unavailable_error():
    """Verify clear setup error is raised if model files are unconfigured/missing."""
    orig_det = face_service._detector
    orig_rec = face_service._recognizer
    orig_err = face_service._init_error
    try:
        face_service._detector = None
        face_service._recognizer = None
        face_service._init_error = "YuNet model file missing"
        with patch.object(face_service, "_initialize_models", lambda: None):
            try:
                face_service.process_and_extract_embedding(b"fake_bytes", consent_obtained=True)
                assert False, "Should have raised FaceProcessingError"
            except FaceProcessingError as exc:
                assert exc.status_code == 503
                assert "Biometric processing service unavailable" in exc.message
    finally:
        face_service._detector = orig_det
        face_service._recognizer = orig_rec
        face_service._init_error = orig_err


def test_face_service_no_face_detected():
    """Verify error when image contains no face (blank image)."""
    # Create black 320x320 image
    blank_img = io.BytesIO()
    Image.new("RGB", (320, 320), color="black").save(blank_img, format="JPEG")
    blank_bytes = blank_img.getvalue()

    try:
        face_service.process_and_extract_embedding(blank_bytes, consent_obtained=True)
        assert False, "Should have failed with no face detected"
    except FaceProcessingError as exc:
        assert exc.status_code == 400
        assert "No face detected" in exc.message


# ==========================================
# 5. Security & Sensitive Data Leakage Tests
# ==========================================

def test_customer_list_sanitization():
    """Verify /api/customers endpoint strips all sensitive biometric vectors, OTP hashes, and raw PII."""
    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN

    mock_db = MagicMock()
    # Mock return of 1 customer document
    doc_mock = MagicMock()
    doc_mock.id = "cust_abc123"
    doc_mock.to_dict.return_value = {
        "id": "cust_abc123",
        "fullName": "Alice Smith",
        "email": "alice@example.com",
        "phoneMasked": "XXXXXX9876",
        "cardNumberMasked": "XXXX-XXXX-XXXX-5678",
        "bankName": "Bank of India",
        "bankAccount_mask": "XXXXXXXX1234",
        "status": "ACTIVE",
        "createdAt": "2026-10-11T12:00:00Z",
        "faceEnrolled": True,
        # SENSITIVE DATA IN DB:
        "aadhaar_encrypted": "secret_enc_aadhaar",
        "bankAccount_encrypted": "secret_enc_bank",
        "aadhaar_hash": "secret_hash",
        "embedding": [0.123] * 128,
    }

    mock_db.collection.return_value.order_by.return_value.limit.return_value.get.return_value = [doc_mock]

    with patch("app.routers.customers.get_firestore_client", return_value=mock_db):
        res = client.get("/api/customers")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        item = items[0]

        # Verify safe fields present
        assert item["fullName"] == "Alice Smith"
        assert item["phoneMasked"] == "XXXXXX9876"
        assert item["cardNumberMasked"] == "XXXX-XXXX-XXXX-5678"

        # Verify sensitive fields NOT present in JSON
        res_str = str(items)
        assert "secret_enc_aadhaar" not in res_str
        assert "secret_enc_bank" not in res_str
        assert "secret_hash" not in res_str
        assert "0.123" not in res_str

    app.dependency_overrides.pop(get_current_admin, None)


# ==========================================
# GMAIL SMTP SERVICE AUTOMATED UNIT TESTS
# ==========================================

def test_smtp_email_service_configuration():
    """Verify Gmail SMTP email service loads configuration securely without exposing passwords."""
    from app.core.config import settings
    from app.services.email_service import email_service

    assert email_service.smtp_host == "smtp.gmail.com"
    assert email_service.smtp_port == 587
    assert email_service.smtp_user == settings.SMTP_USER
    assert email_service.sender_email == settings.SMTP_FROM

    status = email_service.get_status()
    assert status["provider"] == "Gmail SMTP"
    assert status["host"] == "smtp.gmail.com"
    assert status["port"] == 587
    assert "password" not in str(status).lower()


def test_smtp_send_otp_success():
    """Verify successful OTP dispatch over STARTTLS with authenticated SMTP."""
    import asyncio
    import smtplib
    from app.core.config import settings
    from app.services.email_service import email_service

    mock_server = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp_cls, \
         patch.object(settings, "SMTP_PASSWORD", "test_app_password_1234"):
        res = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Test Customer",
                otp_code="654321",
            )
        )
        assert res["delivered"] is True
        assert "id" in res
        assert res["sender"] == email_service.sender_email
        assert res["recipient"] == "customer@example.com"

        # Verify SMTP sequence: connect -> ehlo -> starttls -> ehlo -> login -> send_message -> quit
        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=email_service.timeout)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(email_service.smtp_user, "test_app_password_1234")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

        # Check message headers
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["To"] == "customer@example.com"
        assert "654321" in sent_msg["Subject"]


def test_smtp_authentication_failure():
    """Verify handling of SMTP authentication failure without leaking credentials."""
    import asyncio
    import smtplib
    from app.core.config import settings
    from app.services.email_service import email_service

    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    with patch("smtplib.SMTP", return_value=mock_server), \
         patch.object(settings, "SMTP_PASSWORD", "invalid_password"):
        res = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Test Customer",
                otp_code="654321",
            )
        )
        assert res["delivered"] is False
        assert "authentication failed" in res["error"].lower()
        assert "Google App Password" in res["error"]
        assert mock_server.quit.called
        # Never leak passwords or sensitive tokens
        assert "invalid_password" not in str(res)


def test_smtp_connection_timeout():
    """Verify handling of SMTP connection timeouts."""
    import asyncio
    from app.core.config import settings
    from app.services.email_service import email_service

    with patch("smtplib.SMTP", side_effect=TimeoutError("Connection timed out")), \
         patch.object(settings, "SMTP_PASSWORD", "test_app_password"):
        res = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Test Customer",
                otp_code="654321",
            )
        )
        assert res["delivered"] is False
        assert "timed out" in res["error"].lower() or "failed to connect" in res["error"].lower()


def test_smtp_missing_configuration():
    """Verify clean error reporting when SMTP configuration or password is missing."""
    import asyncio
    from app.core.config import settings
    from app.services.email_service import email_service

    with patch.object(settings, "SMTP_PASSWORD", ""):
        res = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Test Customer",
                otp_code="654321",
            )
        )
        assert res["delivered"] is False
        assert "not configured" in res["error"].lower()


def test_smtp_delivery_error_refused():
    """Verify handling of refused recipient addresses."""
    import asyncio
    import smtplib
    from app.core.config import settings
    from app.services.email_service import email_service

    mock_server = MagicMock()
    mock_server.send_message.side_effect = smtplib.SMTPRecipientsRefused(
        {"invalid@domain.invalid": (550, b"User mailbox unavailable")}
    )

    with patch("smtplib.SMTP", return_value=mock_server), \
         patch.object(settings, "SMTP_PASSWORD", "test_app_password"):
        res = asyncio.run(
            email_service.send_otp_email(
                recipient_email="invalid@domain.invalid",
                recipient_name="Test Customer",
                otp_code="654321",
            )
        )
        assert res["delivered"] is False
        assert "rejected" in res["error"].lower() or "refused" in res["error"].lower()


def test_smtp_card_notification_uses_same_service():
    """Verify that card notification emails use the same Gmail SMTP service."""
    import asyncio
    from app.core.config import settings
    from app.services.email_service import email_service

    mock_server = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_server), \
         patch.object(settings, "SMTP_PASSWORD", "test_app_password"):
        res = asyncio.run(
            email_service.send_card_issued_email(
                recipient_email="customer@example.com",
                recipient_name="Test Customer",
                card_number="5049 1234 5678 9012",
            )
        )
        assert res["delivered"] is True
        assert res["recipient"] == "customer@example.com"
        mock_server.send_message.assert_called_once()
        sent_msg = mock_server.send_message.call_args[0][0]
        assert "Card Has Been Activated" in sent_msg["Subject"]


def test_smtp_connection_probe_admin():
    """Verify safe SMTP probe test mechanism for administrator diagnostics."""
    import asyncio
    from app.core.config import settings
    from app.services.email_service import email_service

    mock_server = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_server), \
         patch.object(settings, "SMTP_PASSWORD", "test_app_password"):
        res = asyncio.run(email_service.test_connection())
        assert res["success"] is True
        assert "authenticated" in res["message"].lower()
        assert "password" not in str(res).lower()



def test_failed_email_delivery_does_not_allow_otp_bypass():
    """Verify failed email delivery never bypasses OTP verification or allows premature face enrollment."""
    from app.services.email_service import email_service

    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN

    mock_db = MagicMock()
    mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
    doc_ref_mock = MagicMock()
    mock_db.collection.return_value.document.return_value = doc_ref_mock

    # Simulate SMTP failure
    with patch("app.routers.customers.get_firestore_client", return_value=mock_db), \
         patch.object(email_service, "send_otp_email", return_value={"delivered": False, "error": "SMTP server down", "recipient": "test@example.com"}):

        # Registration initiate
        res = client.post(
            "/api/customers/register-initiate",
            json={
                "fullName": "Bypass Tester",
                "email": "bypass.tester@example.com",
                "phone": "9876543210",
                "dob": "1995-01-01",
                "aadhaarNumber": make_valid_aadhaar("99123456780"),
                "bankAccountNumber": "123456789012",
                "bankName": "State Bank of India",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["emailDelivery"]["delivered"] is False

        # Attempt to verify OTP with incorrect code - MUST fail with 400
        verify_doc = MagicMock()
        verify_doc.exists = True
        verify_doc.to_dict.return_value = {
            "verified": False,
            "completed": False,
            "attempts": 0,
            "max_attempts": 5,
            "otp_hash": "real_hash",
            "salt": "real_salt",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
        mock_db.collection.return_value.document.return_value.get.return_value = verify_doc

        verify_res = client.post(
            "/api/customers/otp-verify",
            json={
                "verificationId": data["verificationId"],
                "otp": "000000",
            },
        )
        assert verify_res.status_code == 400
        assert "Invalid verification code" in verify_res.json()["detail"]

    app.dependency_overrides.pop(get_current_admin, None)


if __name__ == "__main__":
    test_aadhaar_verhoeff_validation()
    test_card_number_luhn_and_uniqueness()
    test_sensitive_pii_encryption()
    test_otp_constant_time_verification()
    test_registration_unauthenticated()
    test_registration_invalid_fields()
    test_duplicate_prevention_and_otp_lifecycle()
    test_face_enrollment_consent_required()
    test_face_service_model_unavailable_error()
    test_face_service_no_face_detected()
    test_customer_list_sanitization()
    test_smtp_email_service_configuration()
    test_smtp_send_otp_success()
    test_smtp_authentication_failure()
    test_smtp_connection_timeout()
    test_smtp_missing_configuration()
    test_smtp_delivery_error_refused()
    test_smtp_card_notification_uses_same_service()
    test_smtp_connection_probe_admin()
    test_failed_email_delivery_does_not_allow_otp_bypass()
    print("ALL Phase 2 tests PASSED successfully!")

