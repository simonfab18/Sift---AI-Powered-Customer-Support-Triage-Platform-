import base64
import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.integrations.gmail.client import get_gmail_attachment
from app.integrations.gmail.mapper import ALLOWED_ATTACHMENT_MIME_TYPES, MAX_ATTACHMENT_SIZE_BYTES
from app.models.gmail_connection import GmailConnection
from app.models.ticket import Ticket
from app.models.ticket_attachment import TicketAttachment
from app.services.audit_log_service import create_audit_log
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.rbac_service import require_membership


logger = logging.getLogger(__name__)


STORED_STATUS = "stored"
NOT_DOWNLOADED_STATUS = "not_downloaded"
BLOCKED_STORAGE_STATUS = "blocked"
CLEAN_SCAN_STATUS = "clean"
INFECTED_SCAN_STATUS = "infected"
NOT_REQUIRED_SCAN_STATUS = "not_required"
UNSCANNED_STATUS = "not_scanned"
EICAR_TEST_SIGNATURE = (
    "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
).encode("ascii")

def utc_now() -> datetime:
    return datetime.now(UTC)


def _storage_configured() -> bool:
    return settings.normalized_attachment_storage_backend == "gcs" and bool(settings.attachment_storage_bucket)


def _require_storage_configured() -> None:
    if not _storage_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachment storage is not configured.",
        )


def _get_attachment_or_404(
    db: Session,
    organization_id: str,
    ticket_id: str,
    attachment_id: str,
    actor: AuthenticatedUser,
) -> TicketAttachment:
    require_membership(db, organization_id, actor)
    ticket_exists = db.scalar(
        select(Ticket.id).where(Ticket.organization_id == organization_id, Ticket.id == ticket_id)
    )
    if ticket_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    attachment = db.scalar(
        select(TicketAttachment).where(
            TicketAttachment.organization_id == organization_id,
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.id == attachment_id,
        )
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


def _validate_attachment_policy(attachment: TicketAttachment) -> None:
    if attachment.policy_status.startswith("blocked"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is blocked by policy.")
    if attachment.size_bytes is not None and attachment.size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        attachment.policy_status = "blocked_size"
        attachment.storage_status = BLOCKED_STORAGE_STATUS
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is too large to store.")
    if attachment.mime_type and attachment.mime_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        attachment.policy_status = "blocked_mime"
        attachment.storage_status = BLOCKED_STORAGE_STATUS
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment MIME type is not allowed.")
    if not attachment.gmail_connection_id or not attachment.gmail_message_id or not attachment.gmail_attachment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is missing Gmail metadata.")


def _decode_gmail_attachment_data(payload: dict) -> bytes:
    data = payload.get("data")
    if not isinstance(data, str) or not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail attachment response did not include file data.")
    padding = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + padding)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail attachment data could not be decoded.") from exc


def _attachment_object_name(attachment: TicketAttachment) -> str:
    return f"orgs/{attachment.organization_id}/tickets/{attachment.ticket_id}/attachments/{attachment.id}"


def _upload_gcs_object(object_name: str, content: bytes, content_type: str | None) -> None:
    from google.cloud import storage

    client = storage.Client(project=settings.google_cloud_project_id)
    bucket = client.bucket(settings.attachment_storage_bucket)
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type=content_type or "application/octet-stream")


def _scan_attachment_content(content: bytes) -> tuple[str, str | None]:
    scanner = settings.normalized_attachment_malware_scanning_backend
    if scanner == "disabled":
        return NOT_REQUIRED_SCAN_STATUS, None
    if scanner != "basic":
        raise RuntimeError("Unsupported attachment malware scanning backend.")
    if EICAR_TEST_SIGNATURE in content:
        return INFECTED_SCAN_STATUS, "Attachment blocked by basic malware scanner."
    return CLEAN_SCAN_STATUS, None


def _block_infected_attachment(
    db: Session,
    attachment: TicketAttachment,
    ticket_id: str,
    actor: AuthenticatedUser,
    note: str,
) -> None:
    attachment.policy_status = "blocked_malware"
    attachment.storage_status = BLOCKED_STORAGE_STATUS
    attachment.scan_status = INFECTED_SCAN_STATUS
    attachment.notes = note
    create_audit_log(
        db,
        attachment.organization_id,
        actor.id,
        "attachment.blocked_malware",
        "ticket_attachment",
        attachment.id,
        metadata={
            "ticket_id": ticket_id,
            "scanner": settings.normalized_attachment_malware_scanning_backend,
        },
    )
    db.commit()


def _attachment_content_disposition(filename: str | None) -> str:
    if not filename:
        return "attachment"
    safe_filename = filename.replace('"', "")
    return f'attachment; filename="{safe_filename}"'


def _generate_gcs_signed_url(object_name: str, filename: str | None) -> str:
    import google.auth
    from google.auth.credentials import Signing
    from google.auth.transport.requests import Request
    from google.cloud import storage

    client = storage.Client(project=settings.google_cloud_project_id)
    bucket = client.bucket(settings.attachment_storage_bucket)
    blob = bucket.blob(object_name)
    signed_url_args = {
        "version": "v4",
        "expiration": timedelta(seconds=settings.attachment_signed_url_ttl_seconds),
        "method": "GET",
        "response_disposition": _attachment_content_disposition(filename),
    }

    credentials = client._credentials
    if isinstance(credentials, Signing):
        return blob.generate_signed_url(**signed_url_args)

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    service_account_email = settings.attachment_signing_service_account_email or getattr(
        credentials, "service_account_email", None
    )
    if not service_account_email:
        raise RuntimeError("Cloud Run credentials do not expose a service account email for GCS signed URLs.")

    return blob.generate_signed_url(
        **signed_url_args,
        service_account_email=service_account_email,
        access_token=credentials.token,
    )


async def store_ticket_attachment(
    db: Session,
    organization_id: str,
    ticket_id: str,
    attachment_id: str,
    actor: AuthenticatedUser,
) -> TicketAttachment:
    _require_storage_configured()
    attachment = _get_attachment_or_404(db, organization_id, ticket_id, attachment_id, actor)
    if attachment.storage_status == STORED_STATUS and attachment.storage_object_name:
        return attachment

    try:
        _validate_attachment_policy(attachment)
        connection = db.get(GmailConnection, attachment.gmail_connection_id)
        if connection is None or connection.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
        if connection.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")

        access_token, _ = await refresh_connection_access_token(db, connection)
        payload = await get_gmail_attachment(access_token, attachment.gmail_message_id, attachment.gmail_attachment_id)
        content = _decode_gmail_attachment_data(payload)
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            attachment.policy_status = "blocked_size"
            attachment.storage_status = BLOCKED_STORAGE_STATUS
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is too large to store.")

        scan_status, scan_note = _scan_attachment_content(content)
        if scan_status == INFECTED_SCAN_STATUS:
            _block_infected_attachment(
                db,
                attachment,
                ticket_id,
                actor,
                scan_note or "Attachment blocked by malware scanner.",
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment failed malware scanning.")

        object_name = _attachment_object_name(attachment)
        _upload_gcs_object(object_name, content, attachment.mime_type)
        attachment.storage_object_name = object_name
        attachment.storage_status = STORED_STATUS
        attachment.scan_status = scan_status
        attachment.stored_at = utc_now()
        create_audit_log(
            db,
            organization_id,
            actor.id,
            "attachment.stored",
            "ticket_attachment",
            attachment.id,
            metadata={"ticket_id": ticket_id, "size_bytes": len(content), "storage_backend": "gcs"},
        )
        db.commit()
        db.refresh(attachment)
        return attachment
    except HTTPException:
        raise
    except Exception as exc:
        attachment.storage_status = "store_failed"
        attachment.scan_status = UNSCANNED_STATUS
        attachment.notes = "Attachment storage failed. Retry after checking storage configuration."
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Attachment storage failed.") from exc


def create_attachment_download_url(
    db: Session,
    organization_id: str,
    ticket_id: str,
    attachment_id: str,
    actor: AuthenticatedUser,
) -> tuple[str, int]:
    _require_storage_configured()
    attachment = _get_attachment_or_404(db, organization_id, ticket_id, attachment_id, actor)
    if attachment.storage_status != STORED_STATUS or not attachment.storage_object_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment has not been stored yet.")
    if attachment.scan_status not in {CLEAN_SCAN_STATUS, NOT_REQUIRED_SCAN_STATUS}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment is not cleared for download.")

    try:
        download_url = _generate_gcs_signed_url(attachment.storage_object_name, attachment.filename)
    except Exception as exc:
        logger.exception(
            "Attachment signed URL generation failed",
            extra={
                "event_name": "attachment.download_url_failed",
                "attachment_id": attachment_id,
                "ticket_id": ticket_id,
            },
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Attachment signed URL generation failed.") from exc

    create_audit_log(
        db,
        organization_id,
        actor.id,
        "attachment.download_url_created",
        "ticket_attachment",
        attachment.id,
        metadata={"ticket_id": ticket_id, "expires_in_seconds": settings.attachment_signed_url_ttl_seconds},
    )
    db.commit()
    return download_url, settings.attachment_signed_url_ttl_seconds
