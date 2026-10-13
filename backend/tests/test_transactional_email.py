"""Unit tests for transactional email providers (Resend, Brevo, SMTP) and OTP delivery resilience."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.email_service import email_service, GmailSMTPEmailService
from app.core.security import get_current_admin


client = TestClient(app)

MOCK_ADMIN = {
    "uid": "test_admin_uid_777",
    "email": "admin@faceatm.local",
    "role": "admin",
}


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_current_admin, None)


# =========================================================================
# PROVIDER AUTO-DETECTION & CONFIGURATION TESTS
# =========================================================================

def test_provider_auto_detection_default_smtp():
    """Verify default provider is SMTP when no API keys are present."""
    with patch.object(settings, "EMAIL_PROVIDER", "auto"), \
         patch.object(settings, "RESEND_API_KEY", None), \
         patch.object(settings, "BREVO_API_KEY", None):
        svc = GmailSMTPEmailService()
        assert svc.provider == "smtp"
        assert svc.smtp_host == "smtp.gmail.com"
        assert svc.smtp_port == 587
        status = svc.get_status()
        assert status["provider"] == "Gmail SMTP"
        assert status["host"] == "smtp.gmail.com"
        assert status["port"] == 587


def test_provider_auto_detection_resend():
    """Verify provider auto-detects Resend when RESEND_API_KEY is configured."""
    with patch.object(settings, "EMAIL_PROVIDER", "auto"), \
         patch.object(settings, "RESEND_API_KEY", "re_test_key_abc123"), \
         patch.object(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"):
        svc = GmailSMTPEmailService()
        assert svc.provider == "resend"
        assert svc.is_configured is True
        assert svc.sender_email == "onboarding@resend.dev"
        status = svc.get_status()
        assert status["provider"] == "Resend API"
        assert status["host"] == "api.resend.com"
        assert status["port"] == 443
        # Crucial security rule: API keys must NEVER be exposed
        assert "re_test_key_abc123" not in str(status)


def test_provider_auto_detection_brevo():
    """Verify provider auto-detects Brevo when BREVO_API_KEY is configured."""
    with patch.object(settings, "EMAIL_PROVIDER", "auto"), \
         patch.object(settings, "RESEND_API_KEY", None), \
         patch.object(settings, "BREVO_API_KEY", "xkeysib-test_key_xyz987"), \
         patch.object(settings, "EMAIL_FROM", "verified@example.com"):
        svc = GmailSMTPEmailService()
        assert svc.provider == "brevo"
        assert svc.is_configured is True
        assert svc.sender_email == "verified@example.com"
        status = svc.get_status()
        assert status["provider"] == "Brevo API"
        assert status["host"] == "api.brevo.com"
        assert status["port"] == 443
        assert "xkeysib-test_key_xyz987" not in str(status)


def test_provider_explicit_override():
    """Verify explicit EMAIL_PROVIDER setting overrides auto-detection."""
    with patch.object(settings, "EMAIL_PROVIDER", "smtp"), \
         patch.object(settings, "RESEND_API_KEY", "re_test_key_abc123"):
        svc = GmailSMTPEmailService()
        assert svc.provider == "smtp"


# =========================================================================
# RESEND HTTPS API DISPATCH TESTS
# =========================================================================

def test_resend_send_otp_success():
    """Verify successful OTP dispatch over Resend HTTPS API (port 443)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "resend_msg_001_success"}

    with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
         patch.object(settings, "RESEND_API_KEY", "re_test_key_123"), \
         patch.object(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:

        result = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Jane Doe",
                otp_code="987654",
                expiry_minutes=10,
            )
        )

        assert result["delivered"] is True
        assert result["id"] == "resend_msg_001_success"
        assert result["provider"] == "Resend API"
        assert result["recipient"] == "customer@example.com"

        # Verify correct HTTPS endpoint and payload structure
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.resend.com/emails"
        payload = call_args[1]["json"]
        assert payload["to"] == ["customer@example.com"]
        assert "987654" in payload["html"]
        assert "Face ATM <onboarding@resend.dev>" in payload["from"]
        # Verify Authorization header contains Bearer
        assert call_args[1]["headers"]["Authorization"] == "Bearer re_test_key_123"


def test_resend_authentication_failure():
    """Verify clean handling of 401/403 Resend API key rejection without credential leaks."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Invalid API key"}

    with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
         patch.object(settings, "RESEND_API_KEY", "re_invalid_secret_key"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):

        result = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Jane Doe",
                otp_code="123456",
            )
        )

        assert result["delivered"] is False
        assert "authentication failed" in result["error"].lower()
        # Ensure secret API key is never in error string
        assert "re_invalid_secret_key" not in result["error"]


def test_resend_network_timeout():
    """Verify graceful handling when Resend API request times out."""
    with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
         patch.object(settings, "RESEND_API_KEY", "re_valid_key"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):

        result = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Jane Doe",
                otp_code="123456",
            )
        )

        assert result["delivered"] is False
        assert "timed out" in result["error"].lower()


# =========================================================================
# BREVO HTTPS API DISPATCH TESTS
# =========================================================================

def test_brevo_send_otp_success():
    """Verify successful OTP dispatch over Brevo HTTPS API."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"messageId": "<brevo_msg_777@brevo.com>"}

    with patch.object(settings, "EMAIL_PROVIDER", "brevo"), \
         patch.object(settings, "BREVO_API_KEY", "xkeysib-test_key"), \
         patch.object(settings, "EMAIL_FROM", "verified@example.com"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:

        result = asyncio.run(
            email_service.send_otp_email(
                recipient_email="customer@example.com",
                recipient_name="Jane Doe",
                otp_code="555666",
            )
        )

        assert result["delivered"] is True
        assert result["id"] == "<brevo_msg_777@brevo.com>"
        assert result["provider"] == "Brevo API"

        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://api.brevo.com/v3/smtp/email"
        assert mock_post.call_args[1]["headers"]["api-key"] == "xkeysib-test_key"


# =========================================================================
# ATTACHMENT DISPATCH TESTS (SECURITY ALERTS & INCIDENT ARTIFACTS)
# =========================================================================

def test_resend_security_alert_with_image_attachment():
    """Verify security alert incident photos are encoded and dispatched as attachments."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "resend_alert_001"}

    fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIFfakejpgdata"

    with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
         patch.object(settings, "RESEND_API_KEY", "re_test_key"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:

        result = asyncio.run(
            email_service.send_security_alert_email(
                recipient_email="owner@example.com",
                recipient_name="Card Owner",
                card_number_masked="4532 •••• •••• 9812",
                attempt_timestamp="2026-10-13 12:00:00 UTC",
                failed_attempts=3,
                is_locked=True,
                image_bytes=fake_image_bytes,
                image_filename="mismatch.jpg",
            )
        )

        assert result["delivered"] is True
        payload = mock_post.call_args[1]["json"]
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["filename"] == "mismatch.jpg"
        assert len(payload["attachments"][0]["content"]) > 0


# =========================================================================
# CONNECTION PROBE TESTS
# =========================================================================

def test_connection_probe_resend():
    """Verify safe connection test probe for Resend API key."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
         patch.object(settings, "RESEND_API_KEY", "re_test_probe_key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):

        res = asyncio.run(email_service.test_connection())
        assert res["success"] is True
        assert res["provider"] == "Resend API"
        assert "re_test_probe_key" not in str(res)


# =========================================================================
# REGISTRATION ENDPOINT RESILIENCE & NO BYPASS TESTS
# =========================================================================

from app.core.crypto import generate_verhoeff_checksum

def make_valid_aadhaar(prefix_11: str = "98765432101") -> str:
    return prefix_11 + generate_verhoeff_checksum(prefix_11)

def test_register_initiate_failure_message_never_reports_false_success():
    """Verify register-initiate does not claim verification code sent if email fails."""
    app.dependency_overrides[get_current_admin] = lambda: MOCK_ADMIN

    mock_db = MagicMock()
    mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
    doc_ref_mock = MagicMock()
    mock_db.collection.return_value.document.return_value = doc_ref_mock

    # Simulate transactional email delivery failure (e.g. SMTP blocked on Render)
    with patch("app.routers.customers.get_firestore_client", return_value=mock_db), \
         patch.object(
             email_service,
             "send_otp_email",
             return_value={
                 "delivered": False,
                 "error": "Failed to connect to SMTP server (smtp.gmail.com:587). Connection timed out or refused.",
                 "recipient": "cust@example.com",
                 "provider": "Gmail SMTP",
             },
         ):

        res = client.post(
            "/api/customers/register-initiate",
            json={
                "fullName": "Test Customer",
                "email": "cust@example.com",
                "phone": "9876543210",
                "dob": "1990-01-01",
                "aadhaarNumber": make_valid_aadhaar("99123456780"),
                "bankAccountNumber": "123456789012",
                "bankName": "HDFC Bank",
            },
        )

        assert res.status_code == 200
        data = res.json()
        assert data["emailDelivery"]["delivered"] is False
        # Crucial: message must NOT falsely report that the verification code was sent
        assert "failed to deliver" in data["message"].lower()
        assert "Verification code sent to" not in data["message"]
