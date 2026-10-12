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


if __name__ == "__main__":
    test_root_endpoint()
    test_health_endpoint()
    test_admin_verify_unauthenticated()
    test_admin_summary_unauthenticated()
    test_admin_verify_invalid_token()
    test_service_account_path_resolution()
    test_firebase_initialization_with_project_id()
    print("All backend tests, security checks, and Firebase Admin verifications PASSED successfully!")
