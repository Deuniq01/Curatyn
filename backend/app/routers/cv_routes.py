from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_client import ai_client
from app.auth import get_current_user
from app.db import get_session
from app.models import CV, User
from app.storage import save_file

router = APIRouter(prefix="/api/cvs", tags=["cvs"])


def _extract_pdf_text(content: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception:
        # Not a real PDF (e.g. a .txt used for local testing) — fall back
        # to treating the bytes as plain text so the pipeline still works.
        return content.decode("utf-8", errors="ignore")


@router.get("")
async def list_cvs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(CV).where(CV.user_id == user.id).order_by(CV.created_at.desc()))
    cvs = result.scalars().all()
    return [{"id": c.id, "label": c.label, "createdAt": c.created_at} for c in cvs]


@router.post("")
async def upload_cv(
    label: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_url = await save_file(content, file.filename or "cv.pdf")
    raw_text = _extract_pdf_text(content)
    embedding = await ai_client.embed(raw_text)

    cv = CV(user_id=user.id, label=label, file_url=file_url, raw_text=raw_text, embedding=embedding)
    session.add(cv)
    await session.commit()
    await session.refresh(cv)
    return {"id": cv.id, "label": cv.label}


@router.delete("/{cv_id}")
async def delete_cv(cv_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(CV).where(CV.id == cv_id, CV.user_id == user.id))
    cv = result.scalar_one_or_none()
    if cv is None:
        raise HTTPException(status_code=404, detail="CV not found")
    await session.delete(cv)
    await session.commit()
    return {"deleted": True}
