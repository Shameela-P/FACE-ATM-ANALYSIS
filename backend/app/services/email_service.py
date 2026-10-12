"""Centralized Gmail SMTP email service module for OTP verification and customer notifications.

Uses Python's built-in smtplib and email.message with TLS/STARTTLS encryption.
Keeps SMTP credentials strictly isolated on the backend server.
Never exposes credentials or plaintext OTPs in logs or API responses.
"""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.core.config import settings

logger = logging.getLogger("face_atm.email_service")


class GmailSMTPEmailService:
    """Service wrapper for interacting reliably with Gmail SMTP over STARTTLS."""

    @property
    def smtp_host(self) -> str:
        """Return configured SMTP host."""
        return (settings.SMTP_HOST or "smtp.gmail.com").strip()

    @property
    def smtp_port(self) -> int:
        """Return configured SMTP port (587 for STARTTLS)."""
        return int(settings.SMTP_PORT or 587)

    @property
    def smtp_user(self) -> str:
        """Return configured Gmail username / sender email."""
        return (settings.SMTP_USER or "").strip()

    @property
    def smtp_password(self) -> str:
        """Return configured Google App Password (never logged)."""
        return (settings.SMTP_PASSWORD or "").strip()

    @property
    def sender_email(self) -> str:
        """Return configured outgoing sender address."""
        from_email = settings.SMTP_FROM or settings.SMTP_USER or "pavithra.workss@gmail.com"
        return from_email.strip().strip('"\'')

    @property
    def timeout(self) -> int:
        """Return SMTP operation timeout in seconds."""
        return getattr(settings, "SMTP_TIMEOUT_SECONDS", 15)

    @property
    def is_configured(self) -> bool:
        """
        Check if Gmail SMTP is configured with host, user, and password.
        Requires an App Password (not the user's personal Google password).
        """
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.smtp_user
            and self.smtp_password
            and len(self.smtp_password) > 0
            and self.smtp_password != "YOUR_GMAIL_APP_PASSWORD"
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Return safe, non-sensitive health/configuration status.
        Crucial security rule: NEVER expose the actual password.
        Does NOT claim delivery has succeeded merely because configuration exists.
        """
        configured = self.is_configured
        return {
            "provider": "Gmail SMTP",
            "configured": configured,
            "host": self.smtp_host,
            "port": self.smtp_port,
            "sender_email": self.sender_email or "Not configured",
            "user": self.smtp_user or "Not configured",
            "phase_2_ready": True,
        }

    def _send_email_sync(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronously establish STARTTLS connection to smtp.gmail.com:587,
        authenticate with Google App Password, and transmit email message (with optional attachments).
        Executed inside threadpool to prevent blocking FastAPI's async loop.
        """
        if not self.is_configured:
            logger.warning("Gmail SMTP not configured; cannot deliver email to %s", recipient_email)
            return {
                "delivered": False,
                "error": "Gmail SMTP is not configured. Please set SMTP_PASSWORD in backend/.env.",
                "recipient": recipient_email,
                "sender": self.sender_email,
            }

        # Build RFC 5322 MIME message
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr(("Face ATM", self.sender_email))
        msg["To"] = recipient_email
        msg_id = make_msgid(domain="faceatm.local")
        msg["Message-ID"] = msg_id

        if plain_content:
            msg.set_content(plain_content)
            msg.add_alternative(html_content, subtype="html")
        else:
            msg.set_content(html_content, subtype="html")

        # Process attachments if present
        if attachments:
            for att in attachments:
                content = att.get("content")
                if content:
                    maintype = att.get("maintype", "application")
                    subtype = att.get("subtype", "octet-stream")
                    filename = att.get("filename", "attachment")
                    msg.add_attachment(
                        content,
                        maintype=maintype,
                        subtype=subtype,
                        filename=filename,
                    )

        context = ssl.create_default_context()
        server = None
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
            server.ehlo()
            # Upgrade insecure connection to TLS
            server.starttls(context=context)
            server.ehlo()
            # Authenticate with Google App Password
            server.login(self.smtp_user, self.smtp_password)
            # Send message
            server.send_message(msg)

            logger.info(
                "Successfully dispatched email to %s via Gmail SMTP (msg_id: %s, from: %s)",
                recipient_email,
                msg_id,
                self.sender_email,
            )
            return {
                "delivered": True,
                "id": msg_id,
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("Gmail SMTP authentication failure for %s: %s", self.smtp_user, getattr(exc, "smtp_error", str(exc)))
            return {
                "delivered": False,
                "error": (
                    "Gmail SMTP authentication failed. Please verify your 16-character "
                    "Google App Password in backend/.env (generate one at myaccount.google.com/apppasswords)."
                ),
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        except (smtplib.SMTPConnectError, ConnectionRefusedError, TimeoutError, OSError) as exc:
            logger.error("Gmail SMTP connection failure to %s:%s: %s", self.smtp_host, self.smtp_port, exc)
            return {
                "delivered": False,
                "error": f"Failed to connect to SMTP server ({self.smtp_host}:{self.smtp_port}). Connection timed out or refused.",
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("Gmail SMTP recipient refused for %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"Recipient address rejected by mail server: {recipient_email}.",
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        except smtplib.SMTPException as exc:
            logger.error("Gmail SMTP delivery error for %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"SMTP delivery failure: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        except Exception as exc:
            logger.error("Unexpected error during SMTP dispatch to %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"Email delivery error: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
            }
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    async def send_otp_email(
        self,
        recipient_email: str,
        recipient_name: str,
        otp_code: str,
        expiry_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        Send a one-time verification passcode (OTP) to the customer's email via Gmail SMTP.
        Does not log the OTP code or secret keys.
        """
        subject = f"Face ATM — Your Verification Code: {otp_code}"
        plain_content = (
            f"Hello {recipient_name},\n\n"
            f"Your Face ATM customer registration verification code is: {otp_code}\n"
            f"This code is valid for {expiry_minutes} minutes.\n\n"
            f"Security Notice: Do not share this code with anyone.\n"
            f"© 2026 Face ATM Biometric Banking System."
        )
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #fbf8f3; margin: 0; padding: 24px; color: #173f35; }}
            .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e7dfd5; box-shadow: 0 4px 12px rgba(23,63,53,0.06); }}
            .header {{ text-align: center; border-bottom: 2px solid #f0e9df; padding-bottom: 20px; margin-bottom: 24px; }}
            .title {{ font-size: 24px; font-weight: 700; color: #173f35; margin: 0; }}
            .badge {{ display: inline-block; background-color: #c85a32; color: #ffffff; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-top: 8px; }}
            .greeting {{ font-size: 16px; margin-bottom: 16px; }}
            .code-box {{ text-align: center; margin: 28px 0; background-color: #f6f1e8; border-radius: 8px; padding: 20px; border: 1px dashed #c85a32; }}
            .otp-code {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #173f35; margin: 0; font-family: monospace; }}
            .expiry-text {{ font-size: 13px; color: #736b5e; margin-top: 8px; }}
            .warning {{ background-color: #fff8eb; border-left: 4px solid #d97706; padding: 12px 16px; border-radius: 4px; font-size: 13px; color: #92400e; margin-top: 24px; }}
            .footer {{ text-align: center; font-size: 12px; color: #8c8275; margin-top: 32px; border-top: 1px solid #f0e9df; padding-top: 16px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 class="title">Face ATM Security Verification</h1>
              <span class="badge">Customer Registration</span>
            </div>
            <p class="greeting">Hello <strong>{recipient_name}</strong>,</p>
            <p>An administrator has initiated your customer registration for the Face ATM system. To verify your email address, please use the following one-time verification code:</p>
            
            <div class="code-box">
              <div class="otp-code">{otp_code}</div>
              <div class="expiry-text">Valid for the next {expiry_minutes} minutes</div>
            </div>

            <div class="warning">
              <strong>Security Notice:</strong> Do not share this code with anyone. Face ATM representatives will never ask for your verification code outside of the official registration terminal.
            </div>

            <div class="footer">
              &copy; 2026 Face ATM — Biometric Banking & Customer Verification System.<br>
              If you did not request this registration, please contact system support immediately.
            </div>
          </div>
        </body>
        </html>
        """

        return await asyncio.to_thread(
            self._send_email_sync,
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
        )

    async def send_card_issued_email(
        self,
        recipient_email: str,
        recipient_name: str,
        card_number: str,
    ) -> Dict[str, Any]:
        """
        Send notification with newly generated customer card number upon successful enrollment.
        Uses Gmail SMTP. Excludes Aadhaar, passwords, or facial embeddings.
        """
        clean_card = card_number.replace(" ", "")
        formatted_card = (
            f"{clean_card[0:4]} {clean_card[4:8]} {clean_card[8:12]} {clean_card[12:16]}"
            if len(clean_card) == 16
            else card_number
        )

        subject = "Welcome to Face ATM — Your Customer Card Has Been Activated"
        plain_content = (
            f"Dear {recipient_name},\n\n"
            f"Your Face ATM customer registration and biometric enrollment are complete.\n"
            f"Card Number: {formatted_card}\n\n"
            f"You may now authenticate at any Face ATM terminal using facial recognition.\n"
            f"Never share your banking credentials or OTPs with anyone.\n\n"
            f"© 2026 Face ATM — Secure Face Authentication & Banking."
        )
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #fbf8f3; margin: 0; padding: 24px; color: #173f35; }}
            .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e7dfd5; box-shadow: 0 4px 12px rgba(23,63,53,0.06); }}
            .header {{ text-align: center; border-bottom: 2px solid #f0e9df; padding-bottom: 20px; margin-bottom: 24px; }}
            .title {{ font-size: 24px; font-weight: 700; color: #173f35; margin: 0; }}
            .badge {{ display: inline-block; background-color: #173f35; color: #fbf8f3; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-top: 8px; }}
            .greeting {{ font-size: 16px; margin-bottom: 16px; }}
            .card-wrapper {{ margin: 28px 0; }}
            .atm-card {{ background: linear-gradient(135deg, #173f35 0%, #0d2822 100%); color: #fbf8f3; border-radius: 14px; padding: 24px 28px; box-shadow: 0 10px 24px rgba(23,63,53,0.3); position: relative; }}
            .card-bank {{ font-size: 18px; font-weight: 700; letter-spacing: 1px; color: #eeddc9; }}
            .card-chip {{ width: 38px; height: 28px; background: linear-gradient(135deg, #d4af37, #aa8012); border-radius: 6px; margin: 18px 0; }}
            .card-number {{ font-size: 22px; font-weight: 700; letter-spacing: 3px; font-family: 'Courier New', monospace; margin: 12px 0; color: #ffffff; }}
            .card-holder {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px; color: #b7a692; margin-top: 14px; }}
            .card-holder-name {{ font-size: 15px; font-weight: 600; color: #fbf8f3; }}
            .info-box {{ background-color: #f6f1e8; border-radius: 8px; padding: 16px 20px; font-size: 14px; line-height: 1.6; margin-top: 24px; border-left: 4px solid #173f35; }}
            .footer {{ text-align: center; font-size: 12px; color: #8c8275; margin-top: 32px; border-top: 1px solid #f0e9df; padding-top: 16px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 class="title">Face ATM Card Issuance</h1>
              <span class="badge">Biometric Enrollment Complete</span>
            </div>
            <p class="greeting">Dear <strong>{recipient_name}</strong>,</p>
            <p>Congratulations! Your customer registration and biometric face enrollment with Face ATM have been completed successfully. Your unique customer card number is active:</p>

            <div class="card-wrapper">
              <div class="atm-card">
                <div class="card-bank">FACE ATM SMART CARD</div>
                <div class="card-chip"></div>
                <div class="card-number">{formatted_card}</div>
                <div class="card-holder">Cardholder</div>
                <div class="card-holder-name">{recipient_name}</div>
              </div>
            </div>

            <div class="info-box">
              <strong>How It Works:</strong>
              <ul>
                <li>Your customer card number is your account identification number.</li>
                <li>Your facial biometrics have been securely enrolled and encrypted.</li>
                <li>At any Face ATM terminal, you will be authenticated using face recognition.</li>
                <li>Never share your banking credentials or OTPs with anyone.</li>
              </ul>
            </div>

            <div class="footer">
              &copy; 2026 Face ATM — Secure Face Authentication & Banking.<br>
              This is an automated system notification.
            </div>
          </div>
        </body>
        </html>
        """

        return await asyncio.to_thread(
            self._send_email_sync,
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
        )

    async def send_security_alert_email(
        self,
        recipient_email: str,
        recipient_name: str,
        card_number_masked: str,
        attempt_timestamp: str,
        failed_attempts: int,
        is_locked: bool,
        lockout_minutes: int = 15,
        lockout_expiry: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_filename: Optional[str] = None,
        approval_id: Optional[str] = None,
        accept_token: Optional[str] = None,
        deny_token: Optional[str] = None,
        accept_url: Optional[str] = None,
        deny_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send security alert notification when face verification fails or card is locked.
        Uses Gmail SMTP over STARTTLS.
        Includes:
        - Security Lockout Active heading
        - Customer name, masked card number
        - Incident timestamp with timezone clearly labelled
        - Clear message that captured face did not match enrolled face
        - Captured failed-attempt image attached as email attachment
        - Two options: ACCEPT and DENY (authenticated via short-lived signed HMAC tokens)
        """
        effective_name = recipient_name or "Valued Customer"
        lock_status_text = (
            f"Temporary lockout active for {lockout_minutes} minutes."
            if is_locked
            else f"Attempt {failed_attempts} failed. 3 failed attempts will trigger a 15-minute temporary card lockout."
        )
        expiry_text = lockout_expiry or f"{lockout_minutes} minutes after attempt timestamp"

        # Compute secure decision URLs if tokens are provided
        if approval_id and accept_token and not accept_url:
            accept_url = f"http://localhost:5173/security-alert?incident={approval_id}&token={accept_token}&action=ACCEPT"
        if approval_id and deny_token and not deny_url:
            deny_url = f"http://localhost:5173/security-alert?incident={approval_id}&token={deny_token}&action=DENY"

        subject = (
            "SECURITY ALERT: Face ATM Verification Failed — Security Lockout Active"
            if is_locked
            else "SECURITY ALERT: Face ATM Verification Attempt Failed"
        )

        plain_content = (
            f"Dear {effective_name},\n\n"
            f"SECURITY ALERT: FACE VERIFICATION MISMATCH\n"
            f"==========================================\n\n"
            f"A facial biometric verification attempt on your Face ATM card did NOT match your enrolled face profile.\n\n"
            f"Incident Details:\n"
            f"- Customer Name: {effective_name}\n"
            f"- Card Number: {card_number_masked}\n"
            f"- Incident Timestamp: {attempt_timestamp}\n"
            f"- Failed Attempts: {failed_attempts} / 3\n"
            f"- Lockout Status: {'LOCKED (15 minutes)' if is_locked else 'Active warning'}\n"
            f"- Lockout Expiry: {expiry_text}\n\n"
            f"Captured Photo:\n"
            f"{'The latest photo captured at the terminal during this failed attempt is attached to this email (failed_attempt_capture.jpg).' if image_bytes else 'Snapshot recorded by terminal sensor.'}\n\n"
            f"Response Options (Card Owner Action Required):\n"
            f"1. ACCEPT Attempt:\n"
            f"   If you or someone authorized by you attempted this login, select ACCEPT to unlock your card.\n"
            f"   Notice: The customer at the ATM terminal must still pass facial biometric verification before any transaction is permitted. Accepting this alert will NOT bypass face matching.\n"
            f"   Link: {accept_url if accept_url else 'Please contact bank administration'}\n\n"
            f"2. DENY Attempt:\n"
            f"   If you did NOT authorize this attempt, select DENY to immediately block the suspicious attempt and keep your card locked.\n"
            f"   Link: {deny_url if deny_url else 'Please contact bank administration'}\n\n"
            f"© 2026 Face ATM — Biometric Banking Security Team."
        )

        attachment_note_html = ""
        if image_bytes:
            attachment_note_html = """
            <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 14px 18px; margin: 18px 0; font-size: 13px; color: #1e40af;">
              <strong>📸 Latest Captured Attempt Photo Attached:</strong><br>
              The actual camera frame captured at the ATM terminal during this failed verification attempt has been securely attached to this email (<code>failed_attempt_capture.jpg</code>) for your review.
            </div>
            """

        action_buttons_html = ""
        if accept_url and deny_url:
            action_buttons_html = f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 22px; margin: 24px 0; text-align: center;">
              <h3 style="margin-top: 0; font-size: 16px; color: #0f172a;">Card Owner Authorization Options</h3>
              <p style="font-size: 13px; color: #475569; margin-bottom: 20px;">
                Review the attached captured photo above. Do you recognize and authorize this attempt?
              </p>
              <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap;">
                <a href="{accept_url}" style="background-color: #059669; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(5,150,105,0.25);">
                  ✓ ACCEPT Attempt
                </a>
                <a href="{deny_url}" style="background-color: #dc2626; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(220,38,38,0.25);">
                  ✕ DENY Attempt
                </a>
              </div>
              <p style="font-size: 12px; color: #64748b; margin-top: 16px; margin-bottom: 0;">
                <strong>Security Rule:</strong> Selecting ACCEPT lifts the temporary lockout so the customer can retry. The customer must still pass face matching at the ATM before transactions are permitted. Accepting does not bypass face matching.
              </p>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f7fa; margin: 0; padding: 24px; color: #101828; }}
            .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; padding: 32px; border: 1px solid #e5e7eb; box-shadow: 0 4px 12px rgba(16,24,40,0.06); }}
            .header {{ text-align: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 20px; margin-bottom: 24px; }}
            .alert-badge {{ display: inline-block; background-color: {'#dc2626' if is_locked else '#0f766e'}; color: #ffffff; padding: 6px 16px; border-radius: 999px; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
            .title {{ font-size: 24px; font-weight: 800; color: #101828; margin: 16px 0 0; }}
            .details {{ background: #f8fafc; border-radius: 10px; padding: 20px; margin: 20px 0; border: 1px solid #e2e8f0; border-left: 5px solid {'#dc2626' if is_locked else '#0f766e'}; }}
            .detail-row {{ display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 14px; }}
            .detail-row:last-child {{ margin-bottom: 0; }}
            .detail-label {{ color: #4b5563; font-weight: 600; }}
            .detail-val {{ font-weight: 700; color: #101828; }}
            .mono {{ font-family: monospace; letter-spacing: 1px; }}
            .footer {{ text-align: center; font-size: 12px; color: #6b7280; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <span class="alert-badge">{'Security Lockout Active' if is_locked else 'Security Warning'}</span>
              <h1 class="title">{'Face Verification Mismatch' if is_locked else 'Face Verification Failed'}</h1>
            </div>
            <p>Dear <strong>{effective_name}</strong>,</p>
            <p>A facial biometric verification attempt on your Face ATM card <strong>did not match</strong> the registered facial biometric profile associated with this card.</p>

            <div class="details">
              <div class="detail-row">
                <span class="detail-label">Customer Name:</span>
                <span class="detail-val">{effective_name}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Masked Card Number:</span>
                <span class="detail-val mono">{card_number_masked}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Incident Timestamp:</span>
                <span class="detail-val">{attempt_timestamp}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Failed Attempts:</span>
                <span class="detail-val">{failed_attempts} / 3</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Lockout Duration:</span>
                <span class="detail-val">{lockout_minutes} Minutes</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Lockout Expiry:</span>
                <span class="detail-val">{expiry_text}</span>
              </div>
            </div>

            {attachment_note_html}

            {action_buttons_html}

            <p style="font-size: 13px; line-height: 1.5; color: #4b5563;">
              <strong>Security Protocol:</strong> Your account is protected by multi-tier biometric security. No funds can be withdrawn without passing 3D liveness detection and facial identity matching.
            </p>

            <div class="footer">
              &copy; 2026 Face ATM — Biometric Banking & Customer Verification System.<br>
              Automated security advisory dispatched via Gmail SMTP.
            </div>
          </div>
        </body>
        </html>
        """

        attachments = []
        if image_bytes and len(image_bytes) > 0:
            fn = image_filename or "failed_attempt_capture.jpg"
            subtype = "png" if fn.lower().endswith(".png") else "jpeg"
            attachments.append({
                "content": image_bytes,
                "maintype": "image",
                "subtype": subtype,
                "filename": fn,
            })

        return await asyncio.to_thread(
            self._send_email_sync,
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
            attachments=attachments if attachments else None,
        )


    def test_connection_sync(self) -> Dict[str, Any]:
        """
        Probe the SMTP server connection and authentication without sending an email.
        Safe for administration testing; never exposes passwords.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Gmail SMTP is not configured. Set SMTP_PASSWORD in backend/.env.",
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
            }

        context = ssl.create_default_context()
        server = None
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(self.smtp_user, self.smtp_password)
            return {
                "success": True,
                "message": f"Successfully connected and authenticated with {self.smtp_host}:{self.smtp_port} as {self.smtp_user}.",
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
            }
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "Authentication failed. Check your 16-character Google App Password.",
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Connection probe failed: {str(exc)}",
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
            }
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    async def test_connection(self) -> Dict[str, Any]:
        """Async wrapper for test_connection_sync."""
        return await asyncio.to_thread(self.test_connection_sync)


# Global singleton service instance
email_service = GmailSMTPEmailService()
