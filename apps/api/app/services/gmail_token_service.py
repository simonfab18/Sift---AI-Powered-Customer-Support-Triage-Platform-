from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret
from app.integrations.gmail.client import refresh_gmail_access_token
from app.models.gmail_connection import GmailConnection

REAUTH_ERROR_MARKERS = (
    "invalid_grant",
    "token revoked",
    "revoked",
    "reauthorization_required",
    "invalid refresh token",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_reauthorization_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPException):
        detail = str(exc.detail)
    else:
        detail = str(exc)
    lowered = detail.lower()
    return any(marker in lowered for marker in REAUTH_ERROR_MARKERS)


def mark_reauthorization_required(
    db: Session,
    connection: GmailConnection,
    *,
    reason: str = "token_revoked",
) -> None:
    now = utc_now()
    connection.status = "reauthorization_required"
    connection.sync_status = "reauthorization_required"
    connection.watch_status = "reauthorization_required"
    connection.sync_error_code = "reauthorization_required"
    connection.sync_error_message = "Gmail authorization is no longer valid. Reconnect Gmail to resume sync."
    connection.watch_error = connection.sync_error_message
    connection.reauthorization_required_at = connection.reauthorization_required_at or now
    connection.reauthorization_reason = reason
    connection.last_token_error_at = now
    connection.sync_lock_id = None
    connection.sync_lock_expires_at = None
    db.flush()


def raise_reauthorization_required() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Gmail reauthorization required. Reconnect Gmail to continue.",
    )


async def refresh_connection_access_token(
    db: Session,
    connection: GmailConnection,
    refresh_func=None,
) -> tuple[str, datetime | None]:
    try:
        refresh_token = decrypt_secret(
            connection.encrypted_refresh_token,
            key_version=connection.token_key_version,
        )
        token_refresher = refresh_func or refresh_gmail_access_token
        access_token, expires_at = await token_refresher(refresh_token)
    except Exception as exc:
        if is_reauthorization_error(exc):
            mark_reauthorization_required(db, connection)
            db.commit()
            raise_reauthorization_required()
        raise

    connection.access_token_expires_at = expires_at
    connection.last_token_error_at = None
    if connection.status == "reauthorization_required":
        connection.status = "active"
    if connection.sync_status == "reauthorization_required":
        connection.sync_status = "active"
    if connection.watch_status == "reauthorization_required":
        connection.watch_status = "active"
    connection.reauthorization_required_at = None
    connection.reauthorization_reason = None
    return access_token, expires_at




