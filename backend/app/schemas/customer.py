"""Pydantic schemas and request/response models for customer registration and face enrollment."""

import re
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from app.core.crypto import validate_verhoeff


class CustomerRegistrationRequest(BaseModel):
    """Customer registration initial payload submitted by authorized administrator."""

    fullName: str = Field(..., min_length=2, max_length=100, description="Customer's full legal name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone: str = Field(..., description="10-digit customer mobile phone number")
    dob: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    aadhaarNumber: str = Field(..., description="12-digit Aadhaar number")
    bankAccountNumber: str = Field(..., description="Customer bank account number (9 to 18 digits)")
    bankName: str = Field(..., min_length=2, max_length=100, description="Customer bank institution name")

    @field_validator("fullName")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^[A-Za-z\s\.\'-]{2,100}$", clean):
            raise ValueError("Full name must contain only letters, spaces, hyphens, or periods.")
        return clean

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = re.sub(r"[\s\-\(\)\+]", "", v)
        # Handle +91 prefix
        if clean.startswith("91") and len(clean) == 12:
            clean = clean[2:]
        if not re.match(r"^[6-9]\d{9}$", clean):
            raise ValueError("Phone number must be a valid 10-digit Indian mobile number starting with 6-9.")
        return clean

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        try:
            birth_date = datetime.strptime(v.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Date of birth must be a valid date in YYYY-MM-DD format.")

        today = date.today()
        # Calculate age
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 18:
            raise ValueError("Customer must be at least 18 years old to register.")
        if age > 120:
            raise ValueError("Please provide a valid date of birth.")
        return v.strip()

    @field_validator("aadhaarNumber")
    @classmethod
    def validate_aadhaar(cls, v: str) -> str:
        clean = re.sub(r"[\s\-]", "", v)
        if len(clean) != 12 or not clean.isdigit():
            raise ValueError("Aadhaar number must consist of exactly 12 numeric digits.")
        if not validate_verhoeff(clean):
            raise ValueError("Invalid Aadhaar number: failed official Verhoeff checksum validation.")
        return clean

    @field_validator("bankAccountNumber")
    @classmethod
    def validate_bank_account(cls, v: str) -> str:
        clean = re.sub(r"[\s\-]", "", v)
        if not (9 <= len(clean) <= 18 and clean.isdigit()):
            raise ValueError("Bank account number must be between 9 and 18 numeric digits.")
        return clean

    @field_validator("bankName")
    @classmethod
    def validate_bank_name(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Bank name must be at least 2 characters.")
        return clean


class RegistrationInitiateResponse(BaseModel):
    """Safe response after customer details validated and OTP sent."""

    verificationId: str
    email: str
    customerSummary: Dict[str, str]
    expiresInSeconds: int
    cooldownSeconds: int
    emailDelivery: Dict[str, Any]
    message: str


class OTPResendRequest(BaseModel):
    """Request to resend email verification OTP."""

    verificationId: str


class OTPVerifyRequest(BaseModel):
    """Request to verify the customer OTP."""

    verificationId: str
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator("otp")
    @classmethod
    def validate_otp_format(cls, v: str) -> str:
        clean = v.strip()
        if not clean.isdigit() or len(clean) != 6:
            raise ValueError("Verification code must be exactly 6 numeric digits.")
        return clean


class OTPVerifyResponse(BaseModel):
    """Response after successful OTP verification."""

    verified: bool
    verificationId: str
    customerSummary: Dict[str, str]
    message: str


class FaceEnrollmentRequest(BaseModel):
    """Biometric face enrollment request with camera capture."""

    verificationId: str
    imageBase64: str = Field(..., description="Base64 encoded camera frame (JPEG/PNG/WebP)")
    consentObtained: bool = Field(..., description="Explicit customer consent affirmation")


class FaceEnrollmentResponse(BaseModel):
    """Response after biometric face enrollment and card number issuance."""

    customerId: str
    fullName: str
    email: str
    cardNumber: str  # Displayed only on initial issuance
    cardNumberMasked: str
    faceEnrolled: bool
    confidence: float
    emailDelivery: Dict[str, Any]
    message: str


class ResendCardEmailRequest(BaseModel):
    """Request to safely retry sending customer card details email."""

    customerId: str


class CustomerListItem(BaseModel):
    """Non-sensitive customer record summary for administrative view."""

    id: str
    fullName: str
    email: str
    phoneMasked: str
    cardNumberMasked: str
    bankName: str
    bankAccountMasked: str
    status: str
    createdAt: str
    faceEnrolled: bool
