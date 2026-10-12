"""Health and system status endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.firebase import get_firebase_status
from app.services.email_service import email_service
from app.services.face_service import face_service

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """Root endpoint verifying API availability."""
    return {
        "service": "Face Authentication and Customer Transaction System",
        "phase": 2,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/health")
async def health_check():
    """
    Public health check endpoint.

    Reports runtime operational status and external service configurations
    without exposing any confidential keys or credentials.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "phase": 2,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api": "operational",
            "firebase": get_firebase_status(),
            "email_service": email_service.get_status(),
            "biometric_service": face_service.get_status(),
        },
    }
