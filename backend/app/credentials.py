import json
import os
from pathlib import Path


class CredentialError(RuntimeError):
    pass


def _fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("ASKDATA_CREDENTIAL_KEY", "").encode()
    if not key:
        raise CredentialError("ASKDATA_CREDENTIAL_KEY is required for Phase 2 credentials")
    try:
        return Fernet(key)
    except ValueError as exc:
        raise CredentialError("ASKDATA_CREDENTIAL_KEY must be a Fernet key") from exc


def encrypt_secret(payload: dict) -> str:
    return _fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode()).decode()


def decrypt_secret(token: str) -> dict:
    from cryptography.fernet import InvalidToken
    try:
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except InvalidToken as exc:
        raise CredentialError("credential cannot be decrypted") from exc


def assert_secret_file_permissions(path: Path) -> None:
    if path.exists() and path.stat().st_mode & 0o077:
        raise CredentialError("credential file must not be accessible by group or others")
