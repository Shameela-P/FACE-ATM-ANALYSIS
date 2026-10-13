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
import base64
from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings

logger = logging.getLogger("face_atm.email_service")


class GmailSMTPEmailService:
    """Service wrapper for interacting reliably with transactional email APIs (Resend, Brevo, SendGrid) and Gmail SMTP."""

    @property
    def provider(self) -> str:
        """
        Return active email provider.
        Options: 'resend', 'brevo', 'sendgrid', 'smtp'.
        'auto' detects configured provider in priority: Resend -> Brevo -> SendGrid -> SMTP.
        """
        configured = (getattr(settings, "EMAIL_PROVIDER", "auto") or "auto").strip().lower()
        if configured in ("resend", "brevo", "sendgrid", "smtp"):
            return configured

        # Auto-detection
        resend_key = (getattr(settings, "RESEND_API_KEY", None) or "").strip()
        if resend_key and resend_key != "re_your_resend_api_key_here":
            return "resend"

        brevo_key = (getattr(settings, "BREVO_API_KEY", None) or "").strip()
        if brevo_key and brevo_key != "your_brevo_key_here":
            return "brevo"

        sendgrid_key = (getattr(settings, "SENDGRID_API_KEY", None) or "").strip()
        if sendgrid_key and sendgrid_key != "SG.your_key_here":
            return "sendgrid"

        return "smtp"

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
        p = self.provider
        if p == "resend":
            from_email = getattr(settings, "RESEND_FROM_EMAIL", None) or getattr(settings, "EMAIL_FROM", None)
            if not from_email:
                if settings.SMTP_FROM and not settings.SMTP_FROM.lower().endswith("@gmail.com"):
                    from_email = settings.SMTP_FROM
                else:
                    from_email = "onboarding@resend.dev"
            return from_email.strip().strip('"\'')
        elif p in ("brevo", "sendgrid"):
            from_email = (
                getattr(settings, "EMAIL_FROM", None)
                or settings.SMTP_FROM
                or settings.SMTP_USER
                or "faceAtm2026@gmail.com"
            )
            return from_email.strip().strip('"\'')
        else:
            from_email = settings.SMTP_FROM or settings.SMTP_USER or "pavithra.workss@gmail.com"
            return from_email.strip().strip('"\'')

    @property
    def timeout(self) -> int:
        """Return SMTP/HTTP operation timeout in seconds."""
        return getattr(settings, "SMTP_TIMEOUT_SECONDS", 15)

    @property
    def is_configured(self) -> bool:
        """Check if active email provider has required credentials configured."""
        p = self.provider
        if p == "resend":
            key = (getattr(settings, "RESEND_API_KEY", None) or "").strip()
            return bool(key and key != "re_your_resend_api_key_here")
        elif p == "brevo":
            key = (getattr(settings, "BREVO_API_KEY", None) or "").strip()
            return bool(key and key != "your_brevo_key_here")
        elif p == "sendgrid":
            key = (getattr(settings, "SENDGRID_API_KEY", None) or "").strip()
            return bool(key and key != "SG.your_key_here")
        else:
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
        Crucial security rule: NEVER expose passwords or API keys.
        """
        p = self.provider
        if p == "resend":
            provider_label = "Resend API"
            host_val = "api.resend.com"
            port_val = 443
            user_val = "API Key Authenticated"
        elif p == "brevo":
            provider_label = "Brevo API"
            host_val = "api.brevo.com"
            port_val = 443
            user_val = "API Key Authenticated"
        elif p == "sendgrid":
            provider_label = "SendGrid API"
            host_val = "api.sendgrid.com"
            port_val = 443
            user_val = "API Key Authenticated"
        else:
            provider_label = "Gmail SMTP"
            host_val = self.smtp_host
            port_val = self.smtp_port
            user_val = self.smtp_user or "Not configured"

        return {
            "provider": provider_label,
            "configured": self.is_configured,
            "host": host_val,
            "port": port_val,
            "sender_email": self.sender_email or "Not configured",
            "user": user_val,
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
                "provider": "Gmail SMTP",
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
                "provider": "Gmail SMTP",
            }
        except (smtplib.SMTPConnectError, ConnectionRefusedError, TimeoutError, OSError) as exc:
            logger.error("Gmail SMTP connection failure to %s:%s: %s", self.smtp_host, self.smtp_port, exc)
            return {
                "delivered": False,
                "error": (
                    f"Failed to connect to SMTP server ({self.smtp_host}:{self.smtp_port}). Connection timed out or refused. "
                    "Render blocks outbound SMTP traffic on ports 25, 465, 587. Configure RESEND_API_KEY or BREVO_API_KEY to send emails over HTTPS."
                ),
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Gmail SMTP",
            }
        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("Gmail SMTP recipient refused for %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"Recipient address rejected by mail server: {recipient_email}.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Gmail SMTP",
            }
        except smtplib.SMTPException as exc:
            logger.error("Gmail SMTP delivery error for %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"SMTP delivery failure: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Gmail SMTP",
            }
        except Exception as exc:
            logger.error("Unexpected error during SMTP dispatch to %s: %s", recipient_email, exc)
            return {
                "delivered": False,
                "error": f"Email delivery error: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Gmail SMTP",
            }
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    async def _send_resend_api(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dispatch email via Resend HTTPS REST API."""
        api_key = (getattr(settings, "RESEND_API_KEY", None) or "").strip()
        if not api_key:
            logger.warning("Resend API key missing; cannot deliver email to %s", recipient_email)
            return {
                "delivered": False,
                "error": "Resend API key is not configured. Set RESEND_API_KEY in backend environment.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Resend API",
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        from_addr = self.sender_email
        from_header = f"Face ATM <{from_addr}>" if "<" not in from_addr else from_addr
        payload: Dict[str, Any] = {
            "from": from_header,
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
        }
        if plain_content:
            payload["text"] = plain_content

        if attachments:
            formatted_attachments = []
            for att in attachments:
                content_bytes = att.get("content")
                if content_bytes:
                    formatted_attachments.append({
                        "filename": att.get("filename", "attachment.jpg"),
                        "content": base64.b64encode(content_bytes).decode("ascii"),
                    })
            if formatted_attachments:
                payload["attachments"] = formatted_attachments

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post("https://api.resend.com/emails", json=payload, headers=headers)

            if response.status_code in (200, 201):
                res_data = response.json()
                msg_id = res_data.get("id", "resend_dispatched")
                logger.info("Successfully dispatched email to %s via Resend API (id: %s)", recipient_email, msg_id)
                return {
                    "delivered": True,
                    "id": msg_id,
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Resend API",
                }
            elif response.status_code in (401, 403):
                logger.error("Resend API authentication failure (status %d)", response.status_code)
                return {
                    "delivered": False,
                    "error": "Resend API authentication failed. Please verify your RESEND_API_KEY.",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Resend API",
                }
            else:
                err_text = ""
                try:
                    err_data = response.json()
                    err_text = err_data.get("message") or err_data.get("error") or str(err_data)
                except Exception:
                    err_text = response.text[:200]
                logger.error("Resend API error (%d): %s", response.status_code, err_text)
                return {
                    "delivered": False,
                    "error": f"Resend API error ({response.status_code}): {err_text}",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Resend API",
                }
        except httpx.TimeoutException:
            logger.error("Resend API timeout connecting to api.resend.com for %s", recipient_email)
            return {
                "delivered": False,
                "error": "Resend API request timed out.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Resend API",
            }
        except Exception as exc:
            logger.error("Resend API network exception: %s", exc)
            return {
                "delivered": False,
                "error": f"Failed to send email via Resend API: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Resend API",
            }

    async def _send_brevo_api(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dispatch email via Brevo HTTPS REST API."""
        api_key = (getattr(settings, "BREVO_API_KEY", None) or "").strip()
        if not api_key:
            logger.warning("Brevo API key missing; cannot deliver email to %s", recipient_email)
            return {
                "delivered": False,
                "error": "Brevo API key is not configured. Set BREVO_API_KEY in backend environment.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Brevo API",
            }

        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        payload: Dict[str, Any] = {
            "sender": {"name": "Face ATM", "email": self.sender_email},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_content,
        }
        if plain_content:
            payload["textContent"] = plain_content

        if attachments:
            formatted_attachments = []
            for att in attachments:
                content_bytes = att.get("content")
                if content_bytes:
                    formatted_attachments.append({
                        "name": att.get("filename", "attachment.jpg"),
                        "content": base64.b64encode(content_bytes).decode("ascii"),
                    })
            if formatted_attachments:
                payload["attachment"] = formatted_attachments

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)

            if response.status_code in (200, 201):
                res_data = response.json()
                msg_id = res_data.get("messageId", "brevo_dispatched")
                logger.info("Successfully dispatched email to %s via Brevo API (id: %s)", recipient_email, msg_id)
                return {
                    "delivered": True,
                    "id": msg_id,
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Brevo API",
                }
            elif response.status_code in (401, 403):
                logger.error("Brevo API authentication failure (status %d)", response.status_code)
                return {
                    "delivered": False,
                    "error": "Brevo API authentication failed. Please verify your BREVO_API_KEY.",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Brevo API",
                }
            else:
                err_text = ""
                try:
                    err_data = response.json()
                    err_text = err_data.get("message") or str(err_data)
                except Exception:
                    err_text = response.text[:200]
                logger.error("Brevo API error (%d): %s", response.status_code, err_text)
                return {
                    "delivered": False,
                    "error": f"Brevo API error ({response.status_code}): {err_text}",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "Brevo API",
                }
        except httpx.TimeoutException:
            logger.error("Brevo API timeout connecting to api.brevo.com for %s", recipient_email)
            return {
                "delivered": False,
                "error": "Brevo API request timed out.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Brevo API",
            }
        except Exception as exc:
            logger.error("Brevo API network exception: %s", exc)
            return {
                "delivered": False,
                "error": f"Failed to send email via Brevo API: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "Brevo API",
            }

    async def _send_sendgrid_api(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dispatch email via SendGrid HTTPS REST API."""
        api_key = (getattr(settings, "SENDGRID_API_KEY", None) or "").strip()
        if not api_key:
            return {
                "delivered": False,
                "error": "SendGrid API key is not configured. Set SENDGRID_API_KEY in backend environment.",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "SendGrid API",
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {"email": self.sender_email, "name": "Face ATM"},
            "subject": subject,
            "content": [
                {"type": "text/html", "value": html_content}
            ],
        }
        if plain_content:
            payload["content"].insert(0, {"type": "text/plain", "value": plain_content})

        if attachments:
            formatted_attachments = []
            for att in attachments:
                content_bytes = att.get("content")
                if content_bytes:
                    m = att.get("maintype", "application")
                    s = att.get("subtype", "octet-stream")
                    formatted_attachments.append({
                        "content": base64.b64encode(content_bytes).decode("ascii"),
                        "filename": att.get("filename", "attachment.jpg"),
                        "type": f"{m}/{s}",
                        "disposition": "attachment",
                    })
            if formatted_attachments:
                payload["attachments"] = formatted_attachments

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)

            if response.status_code in (200, 202):
                msg_id = response.headers.get("X-Message-Id", "sendgrid_dispatched")
                return {
                    "delivered": True,
                    "id": msg_id,
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "SendGrid API",
                }
            elif response.status_code in (401, 403):
                return {
                    "delivered": False,
                    "error": "SendGrid API authentication failed. Verify SENDGRID_API_KEY.",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "SendGrid API",
                }
            else:
                return {
                    "delivered": False,
                    "error": f"SendGrid API error ({response.status_code}): {response.text[:200]}",
                    "recipient": recipient_email,
                    "sender": self.sender_email,
                    "provider": "SendGrid API",
                }
        except Exception as exc:
            return {
                "delivered": False,
                "error": f"Failed to send email via SendGrid API: {str(exc)}",
                "recipient": recipient_email,
                "sender": self.sender_email,
                "provider": "SendGrid API",
            }

    async def _dispatch_email(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Route outgoing email to configured provider (Resend, Brevo, SendGrid, or Gmail SMTP)."""
        p = self.provider
        if p == "resend":
            return await self._send_resend_api(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                attachments=attachments,
            )
        elif p == "brevo":
            return await self._send_brevo_api(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                attachments=attachments,
            )
        elif p == "sendgrid":
            return await self._send_sendgrid_api(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                attachments=attachments,
            )
        else:
            return await asyncio.to_thread(
                self._send_email_sync,
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                attachments=attachments,
            )

    async def _test_resend_connection(self) -> Dict[str, Any]:
        """Safe probe for Resend API key authentication."""
        api_key = (getattr(settings, "RESEND_API_KEY", None) or "").strip()
        if not api_key:
            return {"success": False, "error": "RESEND_API_KEY is not configured.", "provider": "Resend API"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get("https://api.resend.com/api-keys", headers={"Authorization": f"Bearer {api_key}"})
            if res.status_code == 200:
                return {"success": True, "message": "Successfully authenticated with Resend API over HTTPS.", "provider": "Resend API"}
            return {"success": False, "error": f"Resend API authentication returned status {res.status_code}.", "provider": "Resend API"}
        except Exception as exc:
            return {"success": False, "error": f"Resend API connection test failed: {str(exc)}", "provider": "Resend API"}

    async def _test_brevo_connection(self) -> Dict[str, Any]:
        """Safe probe for Brevo API key authentication."""
        api_key = (getattr(settings, "BREVO_API_KEY", None) or "").strip()
        if not api_key:
            return {"success": False, "error": "BREVO_API_KEY is not configured.", "provider": "Brevo API"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get("https://api.brevo.com/v3/account", headers={"api-key": api_key, "accept": "application/json"})
            if res.status_code == 200:
                data = res.json()
                return {"success": True, "message": f"Successfully authenticated with Brevo API as {data.get('email', 'account')}.", "provider": "Brevo API"}
            return {"success": False, "error": f"Brevo API authentication returned status {res.status_code}.", "provider": "Brevo API"}
        except Exception as exc:
            return {"success": False, "error": f"Brevo API connection test failed: {str(exc)}", "provider": "Brevo API"}

    async def _test_sendgrid_connection(self) -> Dict[str, Any]:
        """Safe probe for SendGrid API key authentication."""
        api_key = (getattr(settings, "SENDGRID_API_KEY", None) or "").strip()
        if not api_key:
            return {"success": False, "error": "SENDGRID_API_KEY is not configured.", "provider": "SendGrid API"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get("https://api.sendgrid.com/v3/scopes", headers={"Authorization": f"Bearer {api_key}"})
            if res.status_code == 200:
                return {"success": True, "message": "Successfully authenticated with SendGrid API over HTTPS.", "provider": "SendGrid API"}
            return {"success": False, "error": f"SendGrid API authentication returned status {res.status_code}.", "provider": "SendGrid API"}
        except Exception as exc:
            return {"success": False, "error": f"SendGrid API connection test failed: {str(exc)}", "provider": "SendGrid API"}

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

        return await self._dispatch_email(
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

        return await self._dispatch_email(
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

        return await self._dispatch_email(
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
        """Async connection probe supporting both SMTP and transactional HTTP providers."""
        p = self.provider
        if p == "resend":
            return await self._test_resend_connection()
        elif p == "brevo":
            return await self._test_brevo_connection()
        elif p == "sendgrid":
            return await self._test_sendgrid_connection()
        else:
            return await asyncio.to_thread(self.test_connection_sync)


# Global singleton service instance
email_service = GmailSMTPEmailService()
