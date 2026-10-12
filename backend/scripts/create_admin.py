"""Secure CLI provisioning script for creating or promoting the operational administrator.

Admin accounts cannot be registered publicly via the frontend.
This script provisions the administrator directly in Firebase Authentication
and sets the custom user claim {'admin': True}.
"""

import sys
import os
import getpass
import argparse
import re
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.firebase import get_firebase_admin_app, get_firebase_init_error


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 8:
        print("[!] Error: Password must be at least 8 characters long.")
        return False
    return True


def provision_admin(email: str, password: str):
    """Provision admin in Firebase Auth and set custom admin claim."""
    app = get_firebase_admin_app()
    if not app:
        err = get_firebase_init_error() or "Credentials or project ID not configured in backend/.env."
        print("\n[!] Error: Firebase Admin SDK initialization failed.")
        print(f"    Reason: {err}")
        print("    Please check that FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_KEY_PATH")
        print("    are correctly set in your backend/.env file.\n")
        sys.exit(1)

    from firebase_admin import auth, firestore

    print(f"[*] Provisioning operational admin account: {email}")

    # Check if user already exists
    try:
        user = auth.get_user_by_email(email)
        print(f"[*] User already exists (UID: {user.uid}). Updating credentials and admin claim...")
        user = auth.update_user(user.uid, password=password)
    except auth.UserNotFoundError:
        print("[*] Creating new Firebase Authentication user...")
        user = auth.create_user(
            email=email,
            password=password,
            email_verified=True,
            display_name="System Administrator",
        )
        print(f"[+] User created successfully (UID: {user.uid}).")
    except Exception as exc:
        print(f"[!] Authentication service error: {exc}")
        sys.exit(1)

    # Grant admin custom claims (Requirement 8)
    try:
        auth.set_custom_user_claims(user.uid, {"admin": True})
        print("[+] Custom user claim {'admin': True} successfully applied.")
    except Exception as exc:
        print(f"[!] Failed to set custom claims: {exc}")
        sys.exit(1)

    # Record admin metadata in Firestore
    try:
        db = firestore.client()
        admin_ref = db.collection("admins").document(user.uid)
        admin_ref.set(
            {
                "email": email,
                "role": "ADMIN",
                "uid": user.uid,
                "created_at": firestore.SERVER_TIMESTAMP,
                "status": "active",
            },
            merge=True,
        )
        print(f"[+] Firestore admin record created at /admins/{user.uid}.")
    except Exception as exc:
        print(f"[!] Note: Could not record Firestore profile ({exc}). Auth setup succeeded.")

    print("\n==========================================")
    print("  ADMIN ACCOUNT PROVISIONED SUCCESSFULLY  ")
    print("==========================================")
    print(f"Email: {email}")
    print(f"UID:   {user.uid}")
    print("Role:  ADMIN")
    print("You can now log in securely through the Admin Login portal.\n")


def main():
    parser = argparse.ArgumentParser(description="Provision the Operational Administrator Account")
    parser.add_argument("--email", help="Admin email address", default=settings.ADMIN_EMAIL)
    args = parser.parse_args()

    email = args.email
    if not email:
        email = input("Enter admin email address: ").strip()

    if not validate_email(email):
        print(f"[!] Error: Invalid email format: '{email}'")
        sys.exit(1)

    password = getpass.getpass("Enter secure password (min 8 chars): ")
    if not validate_password(password):
        sys.exit(1)

    confirm_password = getpass.getpass("Confirm password: ")
    if password != confirm_password:
        print("[!] Error: Passwords do not match.")
        sys.exit(1)

    provision_admin(email, password)


if __name__ == "__main__":
    main()
