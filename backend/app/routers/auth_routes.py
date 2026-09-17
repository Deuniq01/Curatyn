from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user
from app.db import get_session
from app.models import EmailProviderType, User
from app.schemas import LoginRequest, SignupRequest, TokenResponse
from app.security import hash_password, verify_password

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
    }


# --- OAuth connect/disconnect -------------------------------------------
#
# The real Google/Microsoft OAuth redirect dance (start/callback) needs a
# reachable public redirect URI and live client credentials, so it is not
# exercised in this sandbox. What IS real and tested here is everything
# downstream of "we already have an encrypted refresh token on the user
# row" — see app/token_refresh.py and app/routers/send_routes.py.
#
# For local development without real OAuth, this endpoint lets you attach
# a fake connection so the send/draft flow is reachable end to end.

@router.post("/oauth/dev-connect")
async def dev_connect_email_provider(
    provider: EmailProviderType,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Development-only stand-in for the OAuth callback. Marks the user as
    connected without a real refresh token — only usable together with
    EMAIL_BACKEND=mock, which never calls token_refresh.py."""
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
    await session.commit()
    return {"connected": False}
