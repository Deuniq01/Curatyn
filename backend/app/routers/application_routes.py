"""
Application lifecycle: create (triggers CV matching + first cover-letter
generation), review/edit (FR-REVIEW-001..004), cancel, and the read
endpoints the Final Review screen and history list need.

Send and draft live in send_routes.py — kept separate because that file is
also where idempotency and provider selection live, and mixing "editing"
concerns with "sending" concerns is exactly what PRD Section 29 warns
against.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai_pipeline import generate_cover_letter_and_email, match_cv
from app.auth import get_current_user, require_application_ownership
from app.db import get_session
from app.models import CV, Application, ApplicationEvent, ApplicationEventType, ApplicationStatus, JobDescription, User
from app.schemas import CreateApplicationRequest, UpdateApplicationRequest, UpdateCoverLetterRequest

router = APIRouter(prefix="/api/applications", tags=["applications"])


async def _load_with_relations(session: AsyncSession, application_id: str) -> Application:
    """Eager-loads job_description and selected_cv via selectinload so
    _serialize() never triggers a lazy load outside of an awaited context
    (that would raise MissingGreenlet under the async driver)."""
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.job_description), selectinload(Application.selected_cv))
        .where(Application.id == application_id)
    )
    return result.scalar_one()


async def _log_event(session: AsyncSession, application: Application, event_type: ApplicationEventType, metadata: dict | None = None):
    session.add(ApplicationEvent(application_id=application.id, event_type=event_type, event_metadata=metadata or {}))
    await session.commit()


def _serialize(application: Application) -> dict:
    return {
        "id": application.id,
        "status": application.status.value,
        "companyName": application.job_description.company_name if application.job_description else None,
        "roleTitle": application.job_description.role_title if application.job_description else None,
        "recipientEmail": application.recipient_email,
        "emailSubject": application.email_subject,
        "emailBody": application.email_body,
        "coverLetter": application.cover_letter,
        "matchScore": application.match_score,
        "selectedCvId": application.selected_cv_id,
        "selectedCvLabel": application.selected_cv.label if application.selected_cv else None,
        "emailProvider": application.email_provider.value if application.email_provider else None,
        "providerMessageId": application.provider_message_id,
        "sentAt": application.sent_at,
        "draftId": application.draft_id,
        "lastSendError": application.last_send_error,
        "createdAt": application.created_at,
        "updatedAt": application.updated_at,
    }


def _is_ready_to_send(application: Application) -> bool:
    return bool(
        application.recipient_email
        and application.email_subject
        and application.email_body
        and application.selected_cv_id
        and application.cover_letter
    )


@router.post("")
async def create_application(
    payload: CreateApplicationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    jd_result = await session.execute(
        select(JobDescription).where(JobDescription.id == payload.jobDescriptionId, JobDescription.user_id == user.id)
    )
    jd = jd_result.scalar_one_or_none()
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")
    if jd.embedding is None:
        raise HTTPException(status_code=400, detail="Job description has not finished analysis yet")

    application = Application(user_id=user.id, job_description_id=jd.id, status=ApplicationStatus.CREATED)
    session.add(application)
    await session.commit()
    await session.refresh(application)
    await _log_event(session, application, ApplicationEventType.APPLICATION_CREATED)

    application.status = ApplicationStatus.JD_ANALYZED
    await session.commit()
    await _log_event(session, application, ApplicationEventType.JD_ANALYZED)

    matches = await match_cv(session, user.id, jd.id)
    if not matches:
        raise HTTPException(status_code=400, detail="No CVs with embeddings found — upload a CV first")

    best = matches[0]
    application.selected_cv_id = best["cvId"]
    application.match_score = best["matchScore"]
    application.status = ApplicationStatus.CV_MATCHED
    await session.commit()
    await _log_event(session, application, ApplicationEventType.CV_MATCHED, {"candidates": matches})

    cv_result = await session.execute(select(CV).where(CV.id == best["cvId"]))
    cv = cv_result.scalar_one()

    structured_jd = jd.structured_json or {}
    generated = await generate_cover_letter_and_email(
        structured_jd=structured_jd,
        cv_raw_text=cv.raw_text,
        existing_subject=None,
        existing_body=None,
    )
    application.cover_letter = generated["coverLetter"]
    application.email_subject = generated["emailSubject"]
    application.email_body = generated["emailBody"]
    application.recipient_email = structured_jd.get("applicationEmail")
    application.status = ApplicationStatus.READY_FOR_REVIEW
    await session.commit()
    application = await _load_with_relations(session, application.id)
    await _log_event(session, application, ApplicationEventType.COVER_LETTER_GENERATED)

    return _serialize(application)


@router.get("")
async def list_applications(
    status: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(Application).options(
        selectinload(Application.job_description), selectinload(Application.selected_cv)
    ).where(Application.user_id == user.id).order_by(Application.created_at.desc())
    if status:
        query = query.where(Application.status == ApplicationStatus(status))
    result = await session.execute(query)
    applications = result.scalars().all()
    return [_serialize(a) for a in applications]


@router.get("/{application_id}")
async def get_application(application_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    await require_application_ownership(session, application_id, user)
    application = await _load_with_relations(session, application_id)
    return _serialize(application)


@router.put("/{application_id}")
async def update_application(
    application_id: str,
    payload: UpdateApplicationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """FR-REVIEW-002/003/004: only fields explicitly present in the request
    body are touched. Untouched fields — including anything AI-generated
    that the user has not edited — are left exactly as they were."""
    application = await require_application_ownership(session, application_id, user)

    if application.status in (ApplicationStatus.SENT, ApplicationStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot edit an application in status {application.status.value}")

    updates = payload.model_dump(exclude_unset=True)
    if "recipientEmail" in updates:
        application.recipient_email = updates["recipientEmail"]
    if "emailSubject" in updates:
        application.email_subject = updates["emailSubject"]
    if "emailBody" in updates:
        application.email_body = updates["emailBody"]
    if "selectedCvId" in updates:
        cv_result = await session.execute(select(CV).where(CV.id == updates["selectedCvId"], CV.user_id == user.id))
        cv = cv_result.scalar_one_or_none()
        if cv is None:
            raise HTTPException(status_code=404, detail="CV not found")
        application.selected_cv_id = cv.id

    if application.status not in (ApplicationStatus.SENDING, ApplicationStatus.SAVING_DRAFT):
        application.status = ApplicationStatus.READY_TO_SEND if _is_ready_to_send(application) else ApplicationStatus.USER_REVIEWING

    await session.commit()
    application = await _load_with_relations(session, application.id)
    await _log_event(session, application, ApplicationEventType.USER_REVIEWED, {"fields": list(updates.keys())})
    return _serialize(application)


@router.post("/{application_id}/cover-letter")
async def regenerate_cover_letter(
    application_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_application_ownership(session, application_id, user)
    application = await _load_with_relations(session, application_id)
    if application.selected_cv is None:
        raise HTTPException(status_code=400, detail="No CV selected yet")

    generated = await generate_cover_letter_and_email(
        structured_jd=application.job_description.structured_json or {},
        cv_raw_text=application.selected_cv.raw_text,
        existing_subject=application.email_subject,
        existing_body=application.email_body,
    )
    application.cover_letter = generated["coverLetter"]
    application.email_subject = generated["emailSubject"]  # unchanged if user already had a value — see ai_pipeline.py
    application.email_body = generated["emailBody"]
    await session.commit()
    await _log_event(session, application, ApplicationEventType.COVER_LETTER_GENERATED)
    return _serialize(application)


@router.put("/{application_id}/cover-letter")
async def edit_cover_letter(
    application_id: str,
    payload: UpdateCoverLetterRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    application = await require_application_ownership(session, application_id, user)
    application.cover_letter = payload.coverLetter
    await session.commit()
    application = await _load_with_relations(session, application_id)
    return _serialize(application)


@router.delete("/{application_id}")
async def cancel_application(application_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    application = await require_application_ownership(session, application_id, user)
    application.status = ApplicationStatus.CANCELLED
    await session.commit()
    return {"status": "CANCELLED"}


@router.get("/{application_id}/events")
async def list_events(application_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    application = await require_application_ownership(session, application_id, user)
    result = await session.execute(
        select(ApplicationEvent).where(ApplicationEvent.application_id == application.id).order_by(ApplicationEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [
        {"eventType": e.event_type.value, "provider": e.provider.value if e.provider else None, "metadata": e.event_metadata, "createdAt": e.created_at}
        for e in events
    ]
