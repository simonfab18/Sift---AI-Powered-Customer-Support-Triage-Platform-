import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.integrations.gemini.prompts import TRIAGE_SCHEMA
from app.schemas.ai import TriageOutput

GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
RETRY_IN_PATTERN = re.compile(r"retry in (?P<seconds>\d+(?:\.\d+)?)s", re.IGNORECASE)


class GeminiQuotaExceededError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def parse_retry_after_seconds(response: httpx.Response) -> int | None:
    header_value = response.headers.get("retry-after")
    if header_value:
        try:
            return max(1, int(float(header_value)))
        except ValueError:
            pass
    match = RETRY_IN_PATTERN.search(response.text)
    if match:
        return max(1, int(float(match.group("seconds"))) + 1)
    return None


def is_quota_response(response: httpx.Response) -> bool:
    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return True
    lowered = response.text.lower()
    return "quota" in lowered or "too_many_requests" in lowered or "too many requests" in lowered


def extract_gemini_output_text(raw_output: dict[str, Any]) -> str | None:
    output_text = raw_output.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for step in reversed(raw_output.get("steps", [])):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text

    return None


async def classify_ticket_with_gemini(prompt: str) -> tuple[TriageOutput, dict[str, Any]]:
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini API key is not configured",
        )

    request_body = {
        "model": settings.gemini_model,
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": TRIAGE_SCHEMA,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(
                GEMINI_INTERACTIONS_URL,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json=request_body,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Gemini API from the API server",
        ) from exc

    if response.status_code >= 400:
        error_detail = response.text[:500]
        if is_quota_response(response):
            raise GeminiQuotaExceededError(
                f"Gemini quota exceeded: {error_detail}",
                retry_after_seconds=parse_retry_after_seconds(response),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gemini triage request failed: {error_detail}",
        )

    raw_output = response.json()
    output_text = extract_gemini_output_text(raw_output)
    if not output_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini returned no output text",
        )

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini output was not valid JSON",
        ) from exc

    return TriageOutput.model_validate(parsed), raw_output
