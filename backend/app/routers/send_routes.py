"""
POST /api/applications/:id/send
POST /api/applications/:id/draft

The only place idempotency, ownership, provider selection, and failure
handling meet. On failure, only status and last_send_error change —
cover letter, CV selection, subject, and body are never touched here.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_application_ownership
from app.config import settings
from app.db import get_session
from app.email_provider import EmailAttachment, EmailProviderError, MockEmailProvider
from app.gmail_provider import GmailProvider
from app.idempotency import IdempotencyOutcome, check_idempotency, claim_for_drafting, claim_for_sending
from app.microsoft_provider import MicrosoftProvider
from app.models import Application, ApplicationEvent, ApplicationEventType, ApplicationStatus, CV, EmailProviderType, User
from app.schemas import SendRequest
from app.storage import fetch_cv_pdf_bytes
from app.token_refresh import refresh_access_token

router = APIRouter(prefix="/api/applications", tags=["send"])


async def _build_provider(application: Application, user: User, simulate_failure: bool = False):
    if settings.email_backend == "mock":
        return MockEmailProvider(force_failure=simulate_failure)

    # The application inherits whichever provider the user has connected.
    # (email_provider is set on the User by the OAuth callback, not per-application.)
    provider = application.email_provider or user.email_provider
    if provider is None:
        raise HTTPException(status_code=400, detail="No email provider connected — connect Gmail or Outlook first")
    if not user.encrypted_refresh_token:
        raise HTTPException(status_code=400, detail="Email provider is not connected — reconnect Gmail or Outlook")

    # Record which provider was used, so the application row and its events reflect it.
    if application.email_provider is None:
        application.email_provider = provider

    access_token = await refresh_access_token(provider, user.encrypted_refresh_token)
    if provider == EmailProviderType.GMAIL:
        return GmailProvider(access_token)
    if provider == EmailProviderType.OUTLOOK:
        return MicrosoftProvider(access_token)
    raise HTTPException(status_code=400, detail="Unknown email provider")


async def _log_event(session: AsyncSession, application: Application, event_type: ApplicationEventType, metadata: dict | None = None):
    session.add(ApplicationEvent(
        application_id=application.id,
        event_type=event_type,
        provider=application.email_provider,
        provider_message_id=application.provider_message_id,
        event_metadata=metadata or {},
    ))
    await session.commit()


async def _load_attachment(session: AsyncSession, application: Application) -> EmailAttachment:
    cv_result = await session.execute(select(CV).where(CV.id == application.selected_cv_id))
    cv = cv_result.scalar_one_or_none()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV selected — cannot send without an attachment")
    cv_bytes = await fetch_cv_pdf_bytes(cv.file_url)
    return EmailAttachment(filename=f"{cv.label}.pdf", content_bytes=cv_bytes)


@router.post("/{application_id}/send")
async def send_application(
    application_id: str,
    payload: SendRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    application = await require_application_ownership(session, application_id, user)
    check = await check_idempotency(session, application_id, payload.idempotencyKey)

    if check.outcome == IdempotencyOutcome.ALREADY_SUCCEEDED:
        return {"status": application.status.value, "providerMessageId": application.provider_message_id, "sentAt": application.sent_at}
    if check.outcome == IdempotencyOutcome.ALREADY_FAILED:
        return {"status": application.status.value, "error": application.last_send_error, "retryable": True}
    if check.outcome == IdempotencyOutcome.IN_FLIGHT:
        raise HTTPException(status_code=409, detail="Send already in progress for this application")

    if application.status not in (ApplicationStatus.READY_TO_SEND, ApplicationStatus.SEND_FAILED):
        raise HTTPException(status_code=400, detail=f"Application must be READY_TO_SEND to send, current status is {application.status.value}")

    if not await claim_for_sending(session, application, payload.idempotencyKey):
        recheck = await check_idempotency(session, application_id, payload.idempotencyKey)
        return {"status": recheck.application.status.value}

    await _log_event(session, application, ApplicationEventType.SEND_INITIATED)

    try:
        provider = await _build_provider(application, user, simulate_failure=payload.simulateFailure)
        attachment = await _load_attachment(session, application)

        result = await provider.send_email(
            recipient=application.recipient_email,
            subject=application.email_subject,
            body=application.email_body,
            attachment=attachment,
        )

        application.status = ApplicationStatus.SENT
        application.provider_message_id = result.provider_message_id
        application.sent_at = datetime.now(timezone.utc)
        application.last_send_error = None
        await session.commit()
        await _log_event(session, application, ApplicationEventType.EMAIL_SENT, {"providerMessageId": result.provider_message_id})

        return {"status": "SENT", "providerMessageId": result.provider_message_id, "sentAt": application.sent_at}

    except EmailProviderError as exc:
        application.status = ApplicationStatus.SEND_FAILED
        application.last_send_error = exc.message
        await session.commit()
        await _log_event(session, application, ApplicationEventType.SEND_FAILED, {"error": exc.message, "providerStatus": exc.provider_status})
        return {"status": "SEND_FAILED", "error": exc.message, "retryable": exc.retryable}


@router.post("/{application_id}/draft")
async def save_application_as_draft(
    application_id: str,
    payload: SendRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    application = await require_application_ownership(session, application_id, user)
    check = await check_idempotency(session, application_id, payload.idempotencyKey)

    if check.outcome == IdempotencyOutcome.ALREADY_SUCCEEDED:
        return {"status": application.status.value, "draftId": application.draft_id}
    if check.outcome == IdempotencyOutcome.ALREADY_FAILED:
        return {"status": application.status.value, "error": application.last_send_error, "retryable": True}
    if check.outcome == IdempotencyOutcome.IN_FLIGHT:
        raise HTTPException(status_code=409, detail="Draft creation already in progress")

    if not await claim_for_drafting(session, application, payload.idempotencyKey):
        recheck = await check_idempotency(session, application_id, payload.idempotencyKey)
        return {"status": recheck.application.status.value}

    try:
        provider = await _build_provider(application, user, simulate_failure=payload.simulateFailure)
        attachment = await _load_attachment(session, application)

        result = await provider.create_draft(
            recipient=application.recipient_email,
            subject=application.email_subject,
            body=application.email_body,
            attachment=attachment,
        )

        application.status = ApplicationStatus.DRAFT_CREATED
        application.draft_id = result.draft_id
        application.last_send_error = None
        await session.commit()
        await _log_event(session, application, ApplicationEventType.DRAFT_CREATED)
        return {"status": "DRAFT_CREATED", "draftId": result.draft_id}

    except EmailProviderError as exc:
        application.status = ApplicationStatus.DRAFT_CREATION_FAILED
        application.last_send_error = exc.message
        await session.commit()
        return {"status": "DRAFT_CREATION_FAILED", "error": exc.message, "retryable": exc.retryable}
