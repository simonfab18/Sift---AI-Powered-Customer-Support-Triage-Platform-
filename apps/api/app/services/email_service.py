from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlencode

from app.core.config import settings


@dataclass(frozen=True)
class EmailDeliveryResult:
    status: str
    detail: str | None = None


def invite_signup_url(email: str, organization_id: str, role: str) -> str:
    origin = (settings.frontend_origin or "http://localhost:3000").rstrip("/")
    query = urlencode({"invite_email": email, "organization_id": organization_id, "role": role})
    return f"{origin}/signup?{query}"


def _smtp_ready() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def send_teammate_invite_email(*, to_email: str, organization_name: str, organization_id: str, role: str, invited_by_email: str | None) -> EmailDeliveryResult:
    if not settings.invite_email_enabled:
        return EmailDeliveryResult(status="disabled", detail="Invite email delivery is disabled.")
    if not _smtp_ready():
        return EmailDeliveryResult(status="skipped", detail="SMTP is not configured.")

    signup_url = invite_signup_url(to_email, organization_id, role)
    inviter = invited_by_email or "a workspace admin"
    subject = f"You were invited to Sift for {organization_name}"

    text_body = f"""You were invited to join {organization_name} on Sift as {role}.

{inviter} invited you to help manage Gmail support triage, review AI suggestions, and work the support queue.

Accept the invitation:
{signup_url}

Use this same email address when signing up or signing in: {to_email}

Sift is currently a free Gmail-first pilot. AI replies stay human-approved.
"""

    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111827">
      <h1 style="margin:0 0 12px">Join {organization_name} on Sift</h1>
      <p>{inviter} invited you to join as <strong>{role}</strong>.</p>
      <p>Sift helps teams triage Gmail support, review AI suggestions, and create Gmail drafts only after human approval.</p>
      <p><a href="{signup_url}" style="display:inline-block;background:#756f9f;color:#fff;padding:12px 18px;border-radius:999px;text-decoration:none;font-weight:700">Accept invitation</a></p>
      <p style="color:#647084;font-size:14px">Use this same email address when signing up or signing in: {to_email}</p>
      <p style="color:#647084;font-size:13px">Sift is currently a free Gmail-first pilot.</p>
    </div>
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email or ""))
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - exact SMTP exceptions vary by provider
        return EmailDeliveryResult(status="failed", detail=str(exc))

    return EmailDeliveryResult(status="sent")