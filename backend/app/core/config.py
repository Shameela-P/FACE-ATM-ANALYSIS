"""Application settings and environment configuration."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Base filesystem directories
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent

# Explicitly load .env files into os.environ in order of preference.
# backend/.env takes highest priority and overrides any stale OS-level environment variables.
if (BACKEND_DIR / ".env").exists():
    load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=True)
if (ROOT_DIR / ".env").exists():
    load_dotenv(dotenv_path=ROOT_DIR / ".env", override=False)
if (BACKEND_DIR / ".env.example").exists():
    load_dotenv(dotenv_path=BACKEND_DIR / ".env.example", override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    HOST: str = Field(default="127.0.0.1", description="Server host bind address")
    PORT: int = Field(default=8000, description="Server port")
    ENVIRONMENT: str = Field(default="development", description="Application environment")

    # CORS Origins (comma-separated string or list)
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Allowed CORS origins separated by commas",
    )

    # Primary Admin Account Email
    ADMIN_EMAIL: str = Field(
        default="admin@faceatm.local",
        description="Designated primary operational administrator email",
    )

    # Firebase Admin Configuration
    FIREBASE_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Firebase project identifier",
    )
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: Optional[str] = Field(
        default=None,
        description="Path to Firebase Admin SDK service account credentials JSON file",
    )
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = Field(
        default=None,
        description="Raw JSON string or Base64 encoded JSON string of Firebase service account credentials",
    )

    # Gmail SMTP Configuration (Server-side authenticated SMTP via STARTTLS)
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname (e.g. smtp.gmail.com)",
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port (587 for STARTTLS)",
    )
    SMTP_USER: Optional[str] = Field(
        default="pavithra.workss@gmail.com",
        description="Gmail username/email address",
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="Google 16-character App Password (never normal Gmail password)",
    )
    SMTP_FROM: str = Field(
        default="pavithra.workss@gmail.com",
        description="Sender email address for outgoing system emails",
    )
    SMTP_TIMEOUT_SECONDS: int = Field(
        default=15,
        description="Connection and operation timeout in seconds for SMTP",
    )

    # Transactional Email Provider Configuration (HTTPS API for cloud hosts like Render blocking SMTP ports)
    EMAIL_PROVIDER: str = Field(
        default="auto",
        description="Active email provider: 'auto', 'resend', 'brevo', 'sendgrid', or 'smtp'",
    )
    RESEND_API_KEY: Optional[str] = Field(
        default=None,
        description="Resend API Key (re_...) for transactional email over HTTPS",
    )
    RESEND_FROM_EMAIL: Optional[str] = Field(
        default=None,
        description="Sender address for Resend (e.g. onboarding@resend.dev or verified custom domain)",
    )
    BREVO_API_KEY: Optional[str] = Field(
        default=None,
        description="Brevo API Key for transactional email over HTTPS",
    )
    SENDGRID_API_KEY: Optional[str] = Field(
        default=None,
        description="SendGrid API Key for transactional email over HTTPS",
    )
    EMAIL_FROM: Optional[str] = Field(
        default=None,
        description="Generic sender address for transactional email providers",
    )

    # Phase 2 Security & Biometric Configuration
    DATA_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Base64 encoded 32-byte AES-256 encryption key for sensitive PII data",
    )
    FACE_MODELS_DIR: str = Field(
        default="models",
        description="Directory containing YuNet and SFace ONNX models",
    )
    OTP_EXPIRY_MINUTES: int = Field(
        default=10,
        description="Email OTP validity duration in minutes",
    )
    OTP_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Maximum failed OTP attempts allowed before invalidation",
    )
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(
        default=60,
        description="Cooldown duration before an OTP can be resent",
    )

    # Phase 3 Customer Authentication, Matching, Lockout & ATM Settings
    FACE_MATCH_THRESHOLD: float = Field(
        default=0.40,
        description="Cosine similarity threshold for SFace face matching (OpenCV standard ~0.363 - 0.40)",
    )
    FACE_ANTISPOOF_THRESHOLD: float = Field(
        default=0.60,
        description="Liveness confidence threshold for anti-spoofing verification (0.0 to 1.0)",
    )
    CUSTOMER_SESSION_EXPIRY_MINUTES: int = Field(
        default=15,
        description="Customer ATM session validity in minutes",
    )
    CUSTOMER_MAX_FAILED_ATTEMPTS: int = Field(
        default=3,
        description="Maximum failed face authentication attempts before temporary lockout",
    )
    CUSTOMER_LOCKOUT_MINUTES: int = Field(
        default=15,
        description="Duration of temporary security lockout in minutes after exceeding failed attempts",
    )
    DEFAULT_INITIAL_BALANCE: float = Field(
        default=25000.0,
        description="Initial demo balance in INR credited to newly registered customer accounts",
    )
    ATM_MAX_WITHDRAWAL_AMOUNT: float = Field(
        default=20000.0,
        description="Maximum simulated withdrawal amount allowed per transaction in INR",
    )

    # Security Incident Artifact Storage Settings
    INCIDENT_IMAGES_DIR: str = Field(
        default="data/incident_images",
        description="Private storage directory for captured security incident images",
    )
    INCIDENT_IMAGE_RETENTION_HOURS: int = Field(
        default=168,
        description="Retention duration for incident face images in hours (default: 7 days)",
    )
    INCIDENT_MAX_IMAGE_SIZE_BYTES: int = Field(
        default=5 * 1024 * 1024,
        description="Maximum accepted size in bytes for captured incident image (5MB)",
    )

    model_config = SettingsConfigDict(
        env_file=[
            str(BACKEND_DIR / ".env"),
            str(ROOT_DIR / ".env"),
            str(BACKEND_DIR / ".env.example"),
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS_ORIGINS string into a list of cleaned URLs."""
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()] if self.CORS_ORIGINS else []
        defaults = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"]
        for d in defaults:
            if d not in origins:
                origins.append(d)
        return origins

    def resolve_service_account_path(self) -> Optional[Path]:
        """Resolve service account JSON file path relative to BACKEND_DIR."""
        if not self.FIREBASE_SERVICE_ACCOUNT_KEY_PATH:
            return None
        raw_path = Path(self.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
        if raw_path.is_absolute():
            return raw_path if raw_path.exists() else None
        # Check relative to backend directory
        resolved = (BACKEND_DIR / raw_path).resolve()
        if resolved.exists():
            return resolved
        # Check relative to root directory
        root_resolved = (ROOT_DIR / raw_path).resolve()
        if root_resolved.exists():
            return root_resolved
        # Check relative to current working directory
        cwd_resolved = raw_path.resolve()
        if cwd_resolved.exists():
            return cwd_resolved
        return None

    def resolve_face_models_dir(self) -> Path:
        """Resolve path to face detection and recognition ONNX models."""
        raw_path = Path(self.FACE_MODELS_DIR)
        if raw_path.is_absolute() and raw_path.exists():
            return raw_path
        # Check relative to backend directory
        resolved = (BACKEND_DIR / raw_path).resolve()
        if resolved.exists():
            return resolved
        # Check relative to root directory
        root_resolved = (ROOT_DIR / raw_path).resolve()
        if root_resolved.exists():
            return root_resolved
        # Default fallback to backend / models
        return BACKEND_DIR / "models"

    def resolve_incident_images_dir(self) -> Path:
        """Resolve path to secure private incident images directory."""
        raw_path = Path(self.INCIDENT_IMAGES_DIR)
        if raw_path.is_absolute():
            return raw_path
        return (BACKEND_DIR / raw_path).resolve()


# Global cached settings instance
settings = Settings()
