"""
OAuth credential encryption (Fernet) and password hashing.

Refresh/access tokens are encrypted at rest. The key lives only in the
backend's environment (CURATYN_TOKEN_ENCRYPTION_KEY), never in the database,
never sent to the frontend.
"""
from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _get_fernet() -> Fernet:
    key = settings.curatyn_token_encryption_key
    if not key:
        raise RuntimeError(
            "CURATYN_TOKEN_ENCRYPTION_KEY is not set. Generate one with "
            "Fernet.generate_key() and store it in your secrets manager."
        )
    return Fernet(key.encode("utf-8"))


def encrypt_token(plaintext_token: str) -> str:
    return _get_fernet().encrypt(plaintext_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Stored OAuth token could not be decrypted. The user needs to "
            "reconnect their email provider."
        ) from exc
