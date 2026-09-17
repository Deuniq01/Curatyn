"""
Auth + email-provider OAuth.

Two distinct token systems live here:
  * Curatyn's own JWT session login (signup / login / me), and
  * the Google/Microsoft OAuth grant used to send email on the user's behalf.

The OAuth callback has no Authorization header (the browser is coming back
from Google), so /start signs a short-lived `state` JWT carrying the user id
and the callback verifies it to know who is connecting.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user
from app.config import settings
from app.db import get_session
from app.models import EmailProviderType, User
from app.schemas import LoginRequest, SignupRequest, TokenResponse
from app.security import encrypt_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(payload: SignupRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenResponse(accessToken=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(accessToken=create_access_token(user.id))


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "emailProvider": user.email_provider.value if user.email_provider else None,
        "emailProviderAccountId": user.email_provider_account_id,
    }


# ---------------------------------------------------------------------------
# Real email-provider OAuth (Gmail / Outlook)
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, EmailProviderType] = {
    "gmail": EmailProviderType.GMAIL,
    "outlook": EmailProviderType.OUTLOOK,
}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_ME_URL = "https://graph.microsoft.com/v1.0/me"
MICROSOFT_SCOPES = "offline_access openid email Mail.Send Mail.ReadWrite"


def _make_oauth_state(user_id: str, provider_path: str) -> str:
    payload = {
        "sub": user_id,
        "provider": provider_path,
        "purpose": "oauth_state",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _read_oauth_state(state: str) -> tuple[str, str]:
    payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("purpose") != "oauth_state":
        raise JWTError("wrong purpose")
    return payload["sub"], payload["provider"]


def _frontend_redirect(**params: str) -> RedirectResponse:
    base = settings.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{base}/cvs?{urlencode(params)}")


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, user: User = Depends(get_current_user)):
    """Returns the provider consent URL for the frontend to redirect to."""
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")

    state = _make_oauth_state(user.id, provider)

    if provider == "gmail":
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(status_code=400, detail="Google OAuth is not configured on the server")
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "offline",   # required to receive a refresh token
            "prompt": "consent",        # force a refresh token every time
            "state": state,
        }
        return {"authUrl": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}

    # outlook
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(status_code=400, detail="Microsoft OAuth is not configured on the server")
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_type": "code",
        "scope": MICROSOFT_SCOPES,
        "response_mode": "query",
        "state": state,
    }
    return {"authUrl": f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"}


async def _exchange_google(code: str) -> tuple[str, str, str | None, int | None]:
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        token_resp.raise_for_status()
        tokens = token_resp.json()

        account_email = None
        if tokens.get("access_token"):
            info = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if info.status_code < 400:
                account_email = info.json().get("email")

    return tokens.get("refresh_token"), tokens.get("access_token"), account_email, tokens.get("expires_in")


async def _exchange_microsoft(code: str) -> tuple[str, str, str | None, int | None]:
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(MICROSOFT_TOKEN_URL, data={
            "code": code,
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "redirect_uri": settings.microsoft_redirect_uri,
            "grant_type": "authorization_code",
            "scope": MICROSOFT_SCOPES,
        })
        token_resp.raise_for_status()
        tokens = token_resp.json()

        account_email = None
        if tokens.get("access_token"):
            info = await client.get(
                MICROSOFT_ME_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if info.status_code < 400:
                data = info.json()
                account_email = data.get("mail") or data.get("userPrincipalName")

    return tokens.get("refresh_token"), tokens.get("access_token"), account_email, tokens.get("expires_in")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    if error:
        return _frontend_redirect(email_error=error)
    if provider not in _PROVIDERS or not code or not state:
        return _frontend_redirect(email_error="invalid_request")

    try:
        user_id, state_provider = _read_oauth_state(state)
    except JWTError:
        return _frontend_redirect(email_error="invalid_state")
    if state_provider != provider:
        return _frontend_redirect(email_error="provider_mismatch")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return _frontend_redirect(email_error="user_not_found")

    try:
        if provider == "gmail":
            refresh_token, access_token, account_email, expires_in = await _exchange_google(code)
        else:
            refresh_token, access_token, account_email, expires_in = await _exchange_microsoft(code)
    except httpx.HTTPError:
        return _frontend_redirect(email_error="token_exchange_failed")

    if not refresh_token:
        # No refresh token means we can't send later. Usually a re-consent issue.
        return _frontend_redirect(email_error="no_refresh_token")

    user.email_provider = _PROVIDERS[provider]
    user.email_provider_account_id = account_email or f"{provider}-account"
    user.encrypted_refresh_token = encrypt_token(refresh_token)
    user.encrypted_access_token = encrypt_token(access_token) if access_token else None
    if expires_in:
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    await session.commit()

    return _frontend_redirect(connected=provider)


@router.post("/oauth/dev-connect")
async def dev_connect_email_provider(
    provider: EmailProviderType,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Development-only stand-in for the OAuth callback. Marks the user as
    connected without a real refresh token — only usable together with
    EMAIL_BACKEND=mock, which never calls token_refresh.py. Disabled in
    production (EMAIL_BACKEND=live), where the real OAuth flow above is used."""
    if settings.email_backend == "live":
        raise HTTPException(status_code=404, detail="Not found")
    user.email_provider = provider
    user.email_provider_account_id = f"dev-{provider.value.lower()}@example.com"
    await session.commit()
    return {"connected": provider.value}


@router.delete("/oauth/email-provider")
async def disconnect_email_provider(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    user.email_provider = None
    user.email_provider_account_id = None
    user.encrypted_refresh_token = None
    user.encrypted_access_token = None
    user.token_expires_at = None
    await session.commit()
    return {"connected": False}
