import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import settings


def _fernet_for_key(encryption_key: str | None) -> Fernet:
    if not encryption_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption key is not configured",
        )
    digest = hashlib.sha256(encryption_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _versioned_keyring() -> dict[int, str]:
    try:
        return settings.encryption_keyring_values
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption keyring is not configured correctly",
        ) from exc


def encrypt_secret(value: str) -> str:
    return _fernet_for_key(settings.encryption_key).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, *, key_version: int | None = None) -> str:
    keyring = _versioned_keyring()
    candidate_keys: list[str | None] = []

    if key_version is not None and key_version in keyring:
        candidate_keys.append(keyring[key_version])
    candidate_keys.append(settings.encryption_key)
    if key_version is None:
        candidate_keys.extend(
            key for version, key in sorted(keyring.items()) if version != settings.encryption_key_version
        )

    last_invalid_token: InvalidToken | None = None
    for candidate_key in dict.fromkeys(candidate_keys):
        try:
            return _fernet_for_key(candidate_key).decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            last_invalid_token = exc
            continue

    if last_invalid_token is not None:
        raise last_invalid_token
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Encryption key is not configured",
    )
