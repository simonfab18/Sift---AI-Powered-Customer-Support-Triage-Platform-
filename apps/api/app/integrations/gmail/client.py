from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailHistoryExpiredError(Exception):
    """Raised when Gmail history checkpoint is too old or invalid."""


def _gmail_error_detail(response: httpx.Response, fallback: str) -> str:
    reason = None
    message = None
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        reason = error.get("status")
        message = error.get("message")
        details = error.get("errors")
        if isinstance(details, list) and details:
            first = details[0]
            if isinstance(first, dict):
                reason = reason or first.get("reason")
    parts = [fallback, f"status={response.status_code}"]
    if reason:
        parts.append(f"reason={str(reason)[:120]}")
    if message:
        parts.append(f"message={str(message)[:240]}")
    return "; ".join(parts)


def gmail_expiration_from_millis(value: str | int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except (TypeError, ValueError, OSError):
        return None


async def refresh_gmail_access_token(refresh_token: str) -> tuple[str, datetime | None]:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth client credentials are not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google token endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token refresh failed")

    body = response.json()
    expires_in = body.get("expires_in")
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None
    return body["access_token"], expires_at


async def watch_gmail_mailbox(
    access_token: str,
    topic_name: str,
    label_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"topicName": topic_name}
    if label_ids:
        payload["labelIds"] = label_ids
        payload["labelFilterBehavior"] = "include"

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/users/me/watch",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail watch endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail watch registration failed")

    return response.json()


async def list_gmail_message_ids(
    access_token: str,
    label_ids: list[str],
    unread_only: bool,
    max_results: int = 20,
) -> list[str]:
    params: dict[str, Any] = {"maxResults": max_results}
    if label_ids:
        params["labelIds"] = label_ids
    if unread_only:
        params["q"] = "is:unread"

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/users/me/messages",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail messages endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail message list failed")

    return [message["id"] for message in response.json().get("messages", [])]


async def list_gmail_history(
    access_token: str,
    start_history_id: str,
    page_token: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "startHistoryId": start_history_id,
        "historyTypes": "messageAdded",
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/users/me/history",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail history endpoint from the API server",
        ) from exc

    if response.status_code == 404:
        raise GmailHistoryExpiredError("Gmail history checkpoint is expired or invalid")
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail history list failed")

    return response.json()


async def get_gmail_message(access_token: str, message_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/users/me/messages/{message_id}",
                params={"format": "full"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail message endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_gmail_error_detail(response, "Gmail message fetch failed"),
        )

    return response.json()


async def create_gmail_draft(access_token: str, raw_message: str, thread_id: str | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"raw": raw_message}
    if thread_id:
        message["threadId"] = thread_id

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/users/me/drafts",
                json={"message": message},
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail drafts endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail draft creation failed")

    return response.json()



async def send_gmail_message(access_token: str, raw_message: str, thread_id: str | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"raw": raw_message}
    if thread_id:
        message["threadId"] = thread_id

    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/users/me/messages/send",
                json=message,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail send endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_gmail_error_detail(response, "Gmail message send failed"),
        )

    return response.json()

async def get_gmail_attachment(access_token: str, message_id: str, attachment_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/users/me/messages/{message_id}/attachments/{attachment_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gmail attachment endpoint from the API server",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail attachment fetch failed")

    return response.json()
