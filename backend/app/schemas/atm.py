"""Pydantic schemas for Phase 3 Customer ATM terminal, transactions, and security approvals."""

import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CardValidateRequest(BaseModel):
    """Card number validation request from ATM terminal."""
    cardNumber: str = Field(..., description="16-digit Face ATM card number")

    @field_validator("cardNumber")
    @classmethod
    def validate_card_format(cls, v: str) -> str:
        clean = re.sub(r"[\s-]", "", v)
        if not re.match(r"^\d{16}$", clean):
            raise ValueError("Card number must be exactly 16 digits.")
        return clean


class CardValidateResponse(BaseModel):
    """Response returned upon card number validation."""
    valid: bool
    cardNumberMasked: str
    fullName: str
    isLocked: bool = False
    lockoutRemainingSeconds: Optional[int] = None
    message: str


class FaceLoginRequest(BaseModel):
    """Customer face biometric login request."""
    cardNumber: str = Field(..., description="16-digit Face ATM card number")
    imageBase64: str = Field(..., description="Base64 encoded JPEG/PNG captured frame from camera")

    @field_validator("cardNumber")
    @classmethod
    def clean_card(cls, v: str) -> str:
        clean = re.sub(r"[\s-]", "", v)
        if not re.match(r"^\d{16}$", clean):
            raise ValueError("Card number must be exactly 16 digits.")
        return clean

    @field_validator("imageBase64")
    @classmethod
    def check_image_payload(cls, v: str) -> str:
        if not v or len(v.strip()) < 50:
            raise ValueError("Camera image data is required.")
        return v.strip()


class CustomerSessionResponse(BaseModel):
    """Response returned upon successful biometric verification."""
    success: bool
    sessionToken: str
    customerId: str
    fullName: str
    cardNumberMasked: str
    balance: float
    expiresInMinutes: int
    message: str


class SimulatedTransactionRequest(BaseModel):
    """Simulated withdrawal or deposit transaction request."""
    amount: float = Field(..., description="Transaction amount in INR")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be greater than zero.")
        if v > 20000.0:
            raise ValueError("Maximum ATM transaction limit is ₹20,000 per transaction.")
        if v % 100 != 0:
            raise ValueError("ATM transaction amounts must be in multiples of ₹100 notes (100, 200, 500, etc.).")
        return round(float(v), 2)


class SimulatedTransactionResponse(BaseModel):
    """Response for simulated transaction execution."""
    success: bool
    transactionId: str
    type: str  # WITHDRAWAL or DEPOSIT
    amount: float
    previousBalance: float
    newBalance: float
    timestamp: str
    isSimulated: bool = True
    message: str


class BalanceResponse(BaseModel):
    """Balance inquiry response."""
    customerId: str
    fullName: str
    cardNumberMasked: str
    balance: float
    currency: str = "INR"
    isSimulated: bool = True
    asOf: str


class CustomerDashboardResponse(BaseModel):
    """Complete authenticated customer dashboard payload."""
    customerId: str
    fullName: str
    cardNumberMasked: str
    balance: float
    currency: str = "INR"
    bankName: str
    status: str
    isSimulated: bool = True
    recentTransactions: List[Dict[str, Any]] = []


class SecurityApprovalItem(BaseModel):
    """Security approval record for administrator review."""
    id: str
    customerId: str
    customerName: str
    customerEmail: str
    cardNumberMasked: str
    reason: str
    failedAttempts: int
    status: str  # PENDING, ACCEPTED, DENIED, EXPIRED
    createdAt: str
    expiresAt: str
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[str] = None
    notes: Optional[str] = None


class SecurityApprovalDecisionRequest(BaseModel):
    """Administrator decision payload for a security approval request."""
    decision: str = Field(..., description="'ACCEPT' to unlock customer or 'DENY' to reject")
    notes: Optional[str] = Field(None, max_length=250)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("ACCEPT", "DENY"):
            raise ValueError("Decision must be either 'ACCEPT' or 'DENY'.")
        return upper


class FaceCheckRequest(BaseModel):
    """Fast live camera frame presence check request."""
    imageBase64: str = Field(..., description="Base64 encoded JPEG/PNG frame from ATM camera")


class FaceCheckResponse(BaseModel):
    """Fast live camera frame presence check response."""
    recognizable: bool
    confidence: Optional[float] = None
    message: str


class OwnerAlertDecisionRequest(BaseModel):
    """Card owner authenticated decision request."""
    token: str = Field(..., description="Short-lived HMAC signed owner authorization token")
    decision: str = Field(..., description="'ACCEPT' or 'DENY'")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("ACCEPT", "DENY"):
            raise ValueError("Decision must be either 'ACCEPT' or 'DENY'.")
        return upper


class OwnerIncidentDetailsResponse(BaseModel):
    """Safe non-sensitive incident summary for card owner decision portal."""
    incidentId: str
    cardNumberMasked: str
    customerName: str
    attemptTimestamp: str
    status: str
    used: bool = False
    hasCapturedImage: bool = False
    isLocked: bool = False
    lockoutRemainingSeconds: Optional[int] = None
    message: Optional[str] = None

