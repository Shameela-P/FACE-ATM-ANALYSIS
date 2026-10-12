"""Unit tests for FastAPI backend routes, security, and Firebase configuration."""

import sys
import os
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.config import settings
from app.core.firebase import (
    get_firebase_admin_app,
    is_firebase_admin_ready,
    get_firebase_status,
    get_firebase_init_error,
)

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint responds with online status and Phase 1."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["phase"] in (1, 2)
    assert "Face Authentication" in data["service"]


def test_health_endpoint():
    """Verify health endpoint reports components without exposing secrets."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "components" in data
    assert data["components"]["api"] == "operational"
    assert "email_service" in data["components"]
    assert "firebase" in data["components"]
    # Ensure no secret keys or passwords are exposed
    assert "re_" not in str(data)
    assert "private_key" not in str(data)
    # Check that Firebase status reports initialized
    fb_status = data["components"]["firebase"]
    assert fb_status["initialized"] is True
    assert fb_status["service_account_configured"] is True
    # Check that email service reports Gmail SMTP without exposing credentials
    email_status = data["components"]["email_service"]
    assert email_status["provider"] == "Gmail SMTP"
    assert email_status["host"] == "smtp.gmail.com"
    assert email_status["port"] == 587
    assert "password" not in str(email_status).lower()


def test_admin_verify_unauthenticated():
    """Verify administrative endpoint denies unauthenticated access."""
    response = client.get("/api/admin/verify")
    # Must reject without Bearer token
    assert response.status_code == 401
    assert "detail" in response.json()


def test_admin_summary_unauthenticated():
    """Verify administrative summary endpoint denies unauthenticated access."""
    response = client.get("/api/admin/summary")
    # Must reject without Bearer token
    assert response.status_code == 401
    assert "detail" in response.json()


def test_admin_verify_invalid_token():
    """Verify invalid Bearer tokens are rejected."""
    headers = {"Authorization": "Bearer invalid_fake_token_12345"}
    response = client.get("/api/admin/verify", headers=headers)
    # Must reject invalid token
    assert response.status_code in (401, 503)


def test_service_account_path_resolution():
    """Verify relative service account path resolves accurately from BACKEND_DIR."""
    resolved_path = settings.resolve_service_account_path()
    assert resolved_path is not None
    assert resolved_path.exists()
    assert resolved_path.name == "serviceAccountKey.json"


def test_firebase_initialization_with_project_id():
    """Verify Firebase Admin initializes with valid project ID."""
    app = get_firebase_admin_app()
    assert app is not None
    assert is_firebase_admin_ready() is True
    assert app.project_id == "face-76a11"


def test_cors_preflight_vercel_origin():
    """Verify CORS preflight returns correct headers for Vercel preview and production origins."""
    vercel_origin = "https://face-atm-analysis-pjot-qbemkx77v-shameela5qts-5333s-projects.vercel.app"
    response = client.options(
        "/api/atm/card-validate",
        headers={
            "Origin": vercel_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == vercel_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preserved_on_500_exception():
    """Verify 500 Internal Server Error retains CORS headers so browser shows real error."""
    vercel_origin = "https://face-atm-analysis-pjot-qbemkx77v-shameela5qts-5333s-projects.vercel.app"
    test_client = TestClient(app, raise_server_exceptions=False)
    with patch("app.routers.atm.get_firestore_client", side_effect=RuntimeError("Firestore down")):
        response = test_client.post(
            "/api/atm/card-validate",
            json={"cardNumber": "1234567890123452"},
            headers={"Origin": vercel_origin},
        )
        assert response.status_code == 500
        assert response.headers.get("access-control-allow-origin") == vercel_origin
        assert response.headers.get("access-control-allow-credentials") == "true"
        assert "An internal server error occurred" in response.json()["detail"]


def test_cors_disallows_unauthorized_origin_on_exception():
    """Verify unauthorized origins and unrelated Vercel apps do NOT get CORS headers on 500 errors."""
    test_client = TestClient(app, raise_server_exceptions=False)
    for unauthorized_origin in [
        "https://evil-hacker.com",
        "https://random-other-app.vercel.app",
    ]:
        with patch("app.routers.atm.get_firestore_client", side_effect=RuntimeError("Test error")):
            response = test_client.post(
                "/api/atm/card-validate",
                json={"cardNumber": "1234567890123452"},
                headers={"Origin": unauthorized_origin},
            )
            assert response.status_code == 500
            assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_disallows_unrelated_vercel_origin():
    """Verify unrelated Vercel applications cannot preflight against the API."""
    response = client.options(
        "/api/atm/card-validate",
        headers={
            "Origin": "https://unrelated-project.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    # CORSMiddleware does not return allow-origin for disallowed origins
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_localhost_development():
    """Verify local development on localhost:5173 is permitted."""
    local_origin = "http://localhost:5173"
    response = client.options(
        "/api/atm/card-validate",
        headers={
            "Origin": local_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == local_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


if __name__ == "__main__":
    test_root_endpoint()
    test_health_endpoint()
    test_admin_verify_unauthenticated()
    test_admin_summary_unauthenticated()
    test_admin_verify_invalid_token()
    test_service_account_path_resolution()
    test_firebase_initialization_with_project_id()
    test_cors_preflight_vercel_origin()
    test_cors_preserved_on_500_exception()
    test_cors_disallows_unauthorized_origin_on_exception()
    test_cors_preflight_disallows_unrelated_vercel_origin()
    test_cors_allows_localhost_development()
    print("All backend tests, security checks, and Firebase Admin verifications PASSED successfully!")


