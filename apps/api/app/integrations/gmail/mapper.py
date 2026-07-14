import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

MAX_ATTACHMENT_METADATA_COUNT = 50
MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024
ALLOWED_ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/gif",
    "image/jpeg",
    "image/png",
    "text/csv",
    "text/plain",
}


@dataclass(frozen=True)
class NormalizedGmailAttachment:
    gmail_attachment_id: str | None
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    content_disposition: str | None
    is_inline: bool
    policy_status: str
    notes: str | None = None


@dataclass(frozen=True)
class NormalizedGmailMessage:
    gmail_message_id: str
    gmail_thread_id: str | None
    customer_email: str
    customer_name: str | None
    subject: str
    message_text: str
    message_html: str | None
    received_at: datetime
    attachments: list[NormalizedGmailAttachment]


def _headers_by_name(message: dict[str, Any]) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    return {header.get("name", "").lower(): header.get("value", "") for header in headers}


def _part_headers_by_name(part: dict[str, Any]) -> dict[str, str]:
    headers = part.get("headers", []) or []
    return {header.get("name", "").lower(): header.get("value", "") for header in headers}


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8")).decode("utf-8", errors="replace")


def _walk_parts(part: dict[str, Any]) -> list[dict[str, Any]]:
    parts = [part]
    for child in part.get("parts", []) or []:
        parts.extend(_walk_parts(child))
    return parts


def _body_for_mime(message: dict[str, Any], mime_type: str) -> str | None:
    payload = message.get("payload", {})
    for part in _walk_parts(payload):
        if part.get("mimeType") == mime_type:
            body = _decode_body(part.get("body", {}).get("data"))
            if body.strip():
                return body.strip()
    return None


def _received_at(headers: dict[str, str], internal_date: str | None) -> datetime:
    date_header = headers.get("date")
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass
    if internal_date:
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
    return datetime.now(UTC)


def _attachment_policy_status(mime_type: str | None, size_bytes: int | None) -> tuple[str, str | None]:
    if size_bytes is not None and size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        return "blocked_size", f"Attachment metadata captured, but size exceeds {MAX_ATTACHMENT_SIZE_BYTES} bytes."
    if mime_type and mime_type.lower() not in ALLOWED_ATTACHMENT_MIME_TYPES:
        return "blocked_mime", "Attachment metadata captured, but MIME type is not currently allowed for future download."
    return "metadata_only", None


def _normalize_attachments(message: dict[str, Any]) -> list[NormalizedGmailAttachment]:
    attachments: list[NormalizedGmailAttachment] = []
    payload = message.get("payload", {})
    for part in _walk_parts(payload):
        body = part.get("body", {}) or {}
        filename = (part.get("filename") or "").strip() or None
        gmail_attachment_id = body.get("attachmentId")
        if not filename and not gmail_attachment_id:
            continue

        headers = _part_headers_by_name(part)
        content_disposition = headers.get("content-disposition")
        mime_type = part.get("mimeType")
        size_bytes = body.get("size")
        try:
            size_bytes = int(size_bytes) if size_bytes is not None else None
        except (TypeError, ValueError):
            size_bytes = None
        is_inline = bool(content_disposition and content_disposition.lower().startswith("inline"))
        policy_status, notes = _attachment_policy_status(mime_type, size_bytes)
        attachments.append(
            NormalizedGmailAttachment(
                gmail_attachment_id=gmail_attachment_id,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                content_disposition=content_disposition,
                is_inline=is_inline,
                policy_status=policy_status,
                notes=notes,
            )
        )
        if len(attachments) >= MAX_ATTACHMENT_METADATA_COUNT:
            break
    return attachments


def normalize_gmail_message(message: dict[str, Any]) -> NormalizedGmailMessage:
    headers = _headers_by_name(message)
    sender_name, sender_email = parseaddr(headers.get("from", ""))
    message_text = _body_for_mime(message, "text/plain") or message.get("snippet") or ""
    message_html = _body_for_mime(message, "text/html")

    return NormalizedGmailMessage(
        gmail_message_id=message.get("id", ""),
        gmail_thread_id=message.get("threadId"),
        customer_email=sender_email or "unknown@example.local",
        customer_name=sender_name or None,
        subject=headers.get("subject") or "Customer support request",
        message_text=message_text.strip() or "No message body available.",
        message_html=message_html,
        received_at=_received_at(headers, message.get("internalDate")),
        attachments=_normalize_attachments(message),
    )
