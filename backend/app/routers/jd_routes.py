from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_pipeline import extract_job_description
from app.auth import get_current_user
from app.db import get_session
from app.models import JobDescription, User
from app.schemas import JDTextRequest

router = APIRouter(prefix="/api/job-descriptions", tags=["job-descriptions"])
logger = logging.getLogger(__name__)


@router.post("")
async def submit_job_description_text(
    payload: JDTextRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    jd = JobDescription(user_id=user.id, source_type="text", raw_input=payload.rawInput)
    session.add(jd)
    await session.commit()
    await session.refresh(jd)

    # Synchronous for MVP simplicity — see 08-execution-plan.md Phase 11 for
    # moving this to a background worker once latency matters.
    try:
        structured = await extract_job_description(session, jd.id)
    except Exception as exc:
        logger.exception("Job description analysis failed")
        raise HTTPException(status_code=502, detail="Job analysis is unavailable. Check the Gemini configuration and try again.") from exc

    return {"id": jd.id, "structured": structured}


@router.get("/{jd_id}")
async def get_job_description(jd_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(JobDescription).where(JobDescription.id == jd_id, JobDescription.user_id == user.id))
    jd = result.scalar_one_or_none()
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")
    return {
        "id": jd.id,
        "companyName": jd.company_name,
        "roleTitle": jd.role_title,
        "structured": jd.structured_json,
    }
