from typing import Any

from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError, decode

from app.core.config import settings

GOOGLE_OIDC_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def verify_google_oidc_token(
    authorization: str | None,
    *,
    expected_audience: str | None,
    expected_service_account_email: str | None,
    identity_name: str,
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Missing {identity_name} bearer token")
    if not expected_audience or not expected_service_account_email:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{identity_name} auth is not configured")

    token = authorization.split(" ", 1)[1]
    try:
        jwks_client = PyJWKClient(GOOGLE_OIDC_CERTS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=VALID_ISSUERS,
        )
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid {identity_name} bearer token") from exc

    if claims.get("email") != expected_service_account_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unexpected {identity_name} service account")
    return claims


def verify_pubsub_oidc_token(authorization: str | None) -> dict[str, Any]:
    return verify_google_oidc_token(
        authorization,
        expected_audience=settings.pubsub_expected_audience,
        expected_service_account_email=settings.pubsub_service_account_email,
        identity_name="Pub/Sub",
    )


def verify_task_pubsub_oidc_token(authorization: str | None) -> dict[str, Any]:
    return verify_google_oidc_token(
        authorization,
        expected_audience=settings.task_oidc_expected_audience,
        expected_service_account_email=settings.task_pubsub_service_account_email,
        identity_name="task Pub/Sub",
    )


def verify_scheduler_oidc_token(authorization: str | None) -> dict[str, Any]:
    return verify_google_oidc_token(
        authorization,
        expected_audience=settings.task_oidc_expected_audience,
        expected_service_account_email=settings.scheduler_service_account_email,
        identity_name="Scheduler",
    )