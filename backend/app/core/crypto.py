"""Cryptographic operations, data encryption, masking, and validation for sensitive customer PII."""

import os
import base64
import hmac
import hashlib
import secrets
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

# Verhoeff algorithm multiplication and permutation tables for Aadhaar checksum validation
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def validate_verhoeff(num_str: str) -> bool:
    """Validate 12-digit Aadhaar number using official Verhoeff checksum algorithm."""
    if not num_str.isdigit() or len(num_str) != 12:
        return False
    # Avoid trivial test strings like 000000000000, 111111111111
    if len(set(num_str)) == 1:
        return False

    c = 0
    reversed_digits = [int(d) for d in reversed(num_str)]
    for i, item in enumerate(reversed_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][item]]
    return c == 0


def generate_verhoeff_checksum(num_str_11: str) -> str:
    """Compute Verhoeff checksum digit for an 11-digit prefix to make a valid 12-digit Aadhaar."""
    c = 0
    reversed_digits = [int(d) for d in reversed(num_str_11)]
    for i, item in enumerate(reversed_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][item]]
    return str(_VERHOEFF_INV[c])


def get_raw_encryption_key() -> bytes:
    """Retrieve or derive a 32-byte AES key from settings."""
    if settings.DATA_ENCRYPTION_KEY:
        try:
            decoded = base64.urlsafe_b64decode(settings.DATA_ENCRYPTION_KEY.encode())
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        # Fallback: hash the string to get 32 bytes
        return hashlib.sha256(settings.DATA_ENCRYPTION_KEY.encode()).digest()

    # Deterministic fallback derived from Firebase Project ID + ADMIN_EMAIL
    seed = f"{settings.FIREBASE_PROJECT_ID or 'face-atm'}:{settings.ADMIN_EMAIL}"
    return hashlib.sha256(seed.encode()).digest()


def encrypt_sensitive_data(plaintext: str) -> str:
    """
    Encrypt sensitive data using authenticated AES-256-GCM.
    Returns URL-safe base64 encoded string containing (12-byte nonce + ciphertext + tag).
    """
    if not plaintext:
        return ""
    key = get_raw_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit unique nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    combined = nonce + ciphertext
    return base64.urlsafe_b64encode(combined).decode("utf-8")


def decrypt_sensitive_data(encrypted_str: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted string.
    Raises ValueError on tampering or invalid key.
    """
    if not encrypted_str:
        return ""
    try:
        combined = base64.urlsafe_b64decode(encrypted_str.encode("utf-8"))
        if len(combined) < 12 + 16:  # 12-byte nonce + 16-byte tag
            raise ValueError("Invalid ciphertext length")
        nonce = combined[:12]
        ciphertext = combined[12:]
        key = get_raw_encryption_key()
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}")


def hash_deterministic(value: str, purpose: str = "") -> str:
    """
    Produce a deterministic keyed HMAC-SHA256 hex digest for lookup and duplicate detection.
    Does not expose plaintext PII in database indexes.
    """
    if not value:
        return ""
    key = get_raw_encryption_key()
    # Normalize value: trimmed and lowercased
    normalized = value.strip().lower()
    msg = f"{purpose}:{normalized}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def mask_aadhaar(aadhaar: str) -> str:
    """Format Aadhaar with standard masking: 'XXXX-XXXX-1234'."""
    clean = aadhaar.replace(" ", "").replace("-", "")
    if len(clean) >= 4:
        return f"XXXX-XXXX-{clean[-4:]}"
    return "XXXX-XXXX-XXXX"


def mask_bank_account(account: str) -> str:
    """Format bank account with masking: 'XXXXXXXX1234'."""
    clean = account.strip()
    if len(clean) >= 4:
        return f"{'X' * (len(clean) - 4)}{clean[-4:]}"
    return "XXXXXXXXXXXX"


def mask_card_number(card: str) -> str:
    """Format 16-digit card number with masking: 'XXXX-XXXX-XXXX-1234'."""
    clean = card.replace(" ", "").replace("-", "")
    if len(clean) >= 4:
        return f"XXXX-XXXX-XXXX-{clean[-4:]}"
    return "XXXX-XXXX-XXXX-XXXX"


def format_card_number_display(card: str) -> str:
    """Format 16-digit card number into groups of 4: '5049 1234 5678 9012'."""
    clean = card.replace(" ", "").replace("-", "")
    if len(clean) == 16:
        return f"{clean[0:4]} {clean[4:8]} {clean[8:12]} {clean[12:16]}"
    return clean


def generate_secure_otp(length: int = 6) -> str:
    """Generate cryptographically secure numeric OTP."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def generate_salt(length: int = 16) -> str:
    """Generate a random hex salt."""
    return secrets.token_hex(length)


def hash_otp(otp: str, salt: str) -> str:
    """Compute HMAC-SHA256 digest of OTP using server key and session salt."""
    key = get_raw_encryption_key()
    msg = f"{salt}:{otp.strip()}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_otp_constant_time(provided_otp: str, salt: str, expected_hash: str) -> bool:
    """Verify provided OTP against expected hash in constant time to prevent timing attacks."""
    actual_hash = hash_otp(provided_otp, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def calculate_luhn_checksum(partial_15: str) -> int:
    """Calculate the 16th Luhn check digit for a 15-digit number."""
    digits = [int(d) for d in partial_15]
    checksum = 0
    # Process from right to left
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # Odd positions from right (doubled)
            doubled = d * 2
            checksum += doubled if doubled < 10 else doubled - 9
        else:
            checksum += d
    return (10 - (checksum % 10)) % 10


def generate_unique_card_number() -> str:
    """
    Generate unpredictable 16-digit ATM card number.
    Uses dedicated Face ATM BIN prefix '5049' (Bank Identification Number),
    followed by 11 cryptographically random digits and a valid Luhn check digit.
    Never derives digits from customer personal PII.
    """
    bin_prefix = "5049"  # Face ATM Issuer Identification Number
    random_11 = "".join(str(secrets.randbelow(10)) for _ in range(11))
    partial_15 = bin_prefix + random_11
    check_digit = calculate_luhn_checksum(partial_15)
    return f"{partial_15}{check_digit}"


def validate_luhn_card_number(card_number: str) -> bool:
    """Verify 16-digit card number against Luhn algorithm."""
    clean = card_number.replace(" ", "").replace("-", "")
    if len(clean) != 16 or not clean.isdigit():
        return False
    digits = [int(d) for d in clean]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled if doubled < 10 else doubled - 9
        else:
            checksum += d
    return checksum % 10 == 0
