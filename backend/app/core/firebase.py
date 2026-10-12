"""Firebase Admin SDK initialization and verification service."""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("face_atm.firebase")

_firebase_app = None
_firebase_initialized = False
_init_error_message: Optional[str] = None


def get_firebase_admin_app():
    """
    Lazily initialize and return the Firebase Admin SDK application instance.

    Reuses existing initialized instance if already active.
    Validates that the service account project matches FIREBASE_PROJECT_ID.
    """
    global _firebase_app, _firebase_initialized, _init_error_message

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Reuse existing Firebase initialization instead of creating conflicting apps
        if firebase_admin._apps:
            _firebase_app = firebase_admin.get_app()
            _firebase_initialized = True
            return _firebase_app

        if _firebase_initialized and _firebase_app is not None:
            return _firebase_app

        from app.core.config import settings

        service_account_path = settings.resolve_service_account_path()
        sa_project_id = None
        cred = None

        if service_account_path and service_account_path.exists():
            try:
                with open(service_account_path, "r", encoding="utf-8") as f:
                    sa_data = json.load(f)
                sa_project_id = sa_data.get("project_id")
            except Exception as exc:
                _init_error_message = f"Failed to parse service account JSON at '{service_account_path.name}': {exc}"
                logger.error("%s", _init_error_message)
                return None

            try:
                cred = credentials.Certificate(str(service_account_path))
                logger.info("Loaded Firebase service account credentials from: %s", service_account_path.name)
            except Exception as exc:
                _init_error_message = f"Failed to create Firebase credentials from '{service_account_path.name}': {exc}"
                logger.error("%s", _init_error_message)
                return None

        configured_project_id = settings.FIREBASE_PROJECT_ID

        # Validate that the service account project matches the configured Firebase project
        if configured_project_id and sa_project_id:
            if configured_project_id != sa_project_id:
                msg = (
                    f"Firebase project ID mismatch: Configured FIREBASE_PROJECT_ID '{configured_project_id}' "
                    f"does not match service account project_id '{sa_project_id}'."
                )
                _init_error_message = msg
                logger.error("%s", msg)
                raise ValueError(msg)

        # Determine effective project ID
        effective_project_id = configured_project_id or sa_project_id

        # Fallback to Application Default Credentials if service account not specified
        if not cred and effective_project_id:
            try:
                cred = credentials.ApplicationDefault()
                logger.info("Using Application Default Credentials for project: %s", effective_project_id)
            except Exception:
                cred = None

        # Fail safely with clear error if neither credentials nor project ID exist
        if not cred and not effective_project_id:
            _init_error_message = (
                "Neither valid service account credentials nor FIREBASE_PROJECT_ID was found. "
                "Configure FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_KEY_PATH in backend/.env."
            )
            logger.warning("%s", _init_error_message)
            return None

        # Initialize with both credentials and explicit project ID
        options = {}
        if effective_project_id:
            options["projectId"] = effective_project_id

        if cred:
            _firebase_app = firebase_admin.initialize_app(cred, options=options)
        else:
            _firebase_app = firebase_admin.initialize_app(options=options)

        _firebase_initialized = True
        _init_error_message = None
        logger.info("Firebase Admin SDK successfully initialized for project: %s", effective_project_id)
        return _firebase_app

    except Exception as exc:
        _init_error_message = str(exc)
        logger.error("Firebase Admin SDK initialization error: %s", exc)
        return None


def is_firebase_admin_ready() -> bool:
    """Return True if Firebase Admin SDK is initialized and ready."""
    app = get_firebase_admin_app()
    return app is not None


def get_firebase_init_error() -> Optional[str]:
    """Return error message from failed initialization, if any."""
    return _init_error_message


def get_firebase_status() -> Dict[str, Any]:
    """Return non-sensitive status information about Firebase Admin."""
    from app.core.config import settings
    ready = is_firebase_admin_ready()
    sa_path = settings.resolve_service_account_path()
    return {
        "initialized": ready,
        "project_id": settings.FIREBASE_PROJECT_ID or "auto-detected",
        "service_account_configured": bool(sa_path and sa_path.exists()),
        "status_detail": _init_error_message if not ready else "operational",
    }


def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """
    Verify a Firebase ID token transmitted from the frontend client.

    Returns the decoded token claims dictionary if valid.
    Raises ValueError or FirebaseError on failure.
    """
    if not is_firebase_admin_ready():
        err = get_firebase_init_error() or "Credentials not configured."
        raise RuntimeError(
            f"Firebase Admin SDK is not configured: {err}"
        )

    from firebase_admin import auth

    # verify_id_token validates signature, expiration, and project audience
    decoded_token = auth.verify_id_token(id_token, check_revoked=True)
    return decoded_token


def get_firestore_client():
    """
    Return initialized Cloud Firestore client instance.
    Raises RuntimeError if Firebase Admin SDK is not ready.
    """
    if not is_firebase_admin_ready():
        err = get_firebase_init_error() or "Credentials not configured."
        raise RuntimeError(f"Firebase Admin SDK is not configured: {err}")

    from firebase_admin import firestore
    return firestore.client()
