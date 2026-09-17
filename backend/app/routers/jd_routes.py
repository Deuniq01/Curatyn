from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_pipeline import extract_job_description
from app.auth import get_current_user
from app.db import get_session
from app.models import JobDescription, User
from app.schemas import JDTextRequest
from app.storage import save_file

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


@router.post("/image")
async def submit_job_description_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    allowed_types = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPEG, or WebP image.")
    content = await file.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be between 1 byte and 10 MB.")
    try:
        image_url = await save_file(content, file.filename or "job-description.png")
        from app.ocr import extract_text_from_image
        raw_text = await extract_text_from_image(content, file.content_type)
        if not raw_text:
            raise RuntimeError("No readable text found in image.")
        jd = JobDescription(user_id=user.id, source_type="text", raw_input=raw_text, image_url=image_url)
        session.add(jd)
        await session.commit()
        await session.refresh(jd)
        structured = await extract_job_description(session, jd.id)
        return {"id": jd.id, "structured": structured}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Job description image analysis failed")
        raise HTTPException(status_code=502, detail="Image job analysis is unavailable. Check the Gemini and storage configuration.") from exc


@router.post("/combined")
async def submit_job_description_combined(
    raw_input: str = Form(""),
    file: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not raw_input.strip() and file is None:
        raise HTTPException(status_code=400, detail="Paste a job description, upload an image, or provide both.")

    image_text = ""
    image_url = None
    if file is not None:
        allowed_types = {"image/png", "image/jpeg", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Upload a PNG, JPEG, or WebP image.")
        content = await file.read()
        if not content or len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image must be between 1 byte and 10 MB.")
        try:
            image_url = await save_file(content, file.filename or "job-description.png")
            from app.ocr import extract_text_from_image
            image_text = await extract_text_from_image(content, file.content_type)
        except Exception as exc:
            logger.exception("Combined job description image analysis failed")
            raise HTTPException(status_code=502, detail="Image job analysis is unavailable. Check the Gemini and storage configuration.") from exc

    combined_text = "\n\n".join(part for part in (raw_input.strip(), image_text.strip()) if part)
    jd = JobDescription(user_id=user.id, source_type="text", raw_input=combined_text, image_url=image_url)
    session.add(jd)
    await session.commit()
    await session.refresh(jd)
    try:
        structured = await extract_job_description(session, jd.id)
        return {"id": jd.id, "structured": structured}
    except Exception as exc:
        logger.exception("Combined job description analysis failed")
        raise HTTPException(status_code=502, detail="Job analysis is unavailable. Check the Gemini configuration and try again.") from exc


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
