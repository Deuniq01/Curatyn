"""
Exchanges a stored, encrypted OAuth refresh token for a fresh short-lived
access token, right before every provider call. The access token returned
here is used to build exactly one GmailProvider/MicrosoftProvider instance
for the current request and is never persisted.
"""
import httpx

from app.config import settings
from app.models import EmailProviderType
from app.security import decrypt_token

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


async def refresh_access_token(provider: EmailProviderType, encrypted_refresh_token: str) -> str:
    refresh_token = decrypt_token(encrypted_refresh_token)

    if provider == EmailProviderType.GMAIL:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
        response.raise_for_status()
        return response.json()["access_token"]

    if provider == EmailProviderType.OUTLOOK:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(MICROSOFT_TOKEN_URL, data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "Mail.Send Mail.ReadWrite offline_access",
            })
        response.raise_for_status()
        return response.json()["access_token"]

    raise ValueError(f"Unknown provider: {provider}")
