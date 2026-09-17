"""
Curatyn AI pipeline: JD extraction, pgvector CV matching, cover letter and
email generation. Talks to app.ai_client, never to a specific model SDK
directly.
"""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_client import ai_client
from app.ocr import extract_text_from_image

JD_EXTRACTION_SYSTEM_PROMPT = """You are a job description parser for Curatyn, a job application assistant.

Given the raw text of a job posting, extract a structured summary. Return
ONLY valid JSON, no markdown fences, no commentary, matching this exact shape:

{
  "companyName": string or null,
  "roleTitle": string or null,
  "location": string or null,
  "seniorityLevel": string or null,
  "requiredSkills": [string, ...],
  "preferredSkills": [string, ...],
  "responsibilities": [string, ...],
  "keyQualifications": [string, ...],
  "applicationEmail": string or null,
  "toneHints": string
}

Rules:
- If a field cannot be determined from the text, use null (or an empty array
  for list fields). Never fabricate a company name, role title, or email
  address that is not present in the source text.
- "toneHints" is one short phrase describing how formal or informal the
  posting reads, used later to match the cover letter's tone.
- applicationEmail should only be populated if an explicit email address for
  applying is present in the text.
"""


async def extract_job_description(session: AsyncSession, job_description_id: str) -> dict:
    row = await session.execute(
        text("SELECT source_type, raw_input, image_url FROM job_descriptions WHERE id = :id"),
        {"id": job_description_id},
    )
    source_type, raw_input, image_url = row.one()

    raw_text = await extract_text_from_image(image_url) if source_type == "image" else raw_input

    completion = await ai_client.complete(system=JD_EXTRACTION_SYSTEM_PROMPT, user=raw_text)
    structured = json.loads(completion)
    embedding = await ai_client.embed(_flatten_jd_for_embedding(structured, raw_text))

    await session.execute(
        text(
            """
            UPDATE job_descriptions
            SET raw_input = :raw_text,
                company_name = :company_name,
                role_title = :role_title,
                structured_json = :structured_json,
                embedding = :embedding
            WHERE id = :id
            """
        ),
        {
            "id": job_description_id,
            "raw_text": raw_text,
            "company_name": structured.get("companyName"),
            "role_title": structured.get("roleTitle"),
            "structured_json": json.dumps(structured),
            "embedding": str(embedding),
        },
    )
    await session.commit()
    return structured


def _flatten_jd_for_embedding(structured: dict, raw_text: str) -> str:
    parts = [
        structured.get("roleTitle") or "",
        structured.get("companyName") or "",
        " ".join(structured.get("requiredSkills", [])),
        " ".join(structured.get("preferredSkills", [])),
        " ".join(structured.get("responsibilities", [])),
        raw_text[:2000],
    ]
    return "\n".join(p for p in parts if p)


async def match_cv(session: AsyncSession, user_id: str, job_description_id: str) -> list[dict]:
    """Ranks every CV the user has by cosine similarity to the JD embedding,
    most similar first, using pgvector's <=> (cosine distance) operator."""
    result = await session.execute(
        text(
            """
            SELECT
                cvs.id,
                cvs.label,
                1 - (cvs.embedding <=> jd.embedding) AS similarity
            FROM cvs
            JOIN job_descriptions jd ON jd.id = :jd_id
            WHERE cvs.user_id = :user_id
              AND cvs.embedding IS NOT NULL
              AND jd.embedding IS NOT NULL
            ORDER BY cvs.embedding <=> jd.embedding ASC
            """
        ),
        {"jd_id": job_description_id, "user_id": user_id},
    )
    rows = result.all()
    return [{"cvId": str(r.id), "label": r.label, "matchScore": round(float(r.similarity), 4)} for r in rows]


COVER_LETTER_SYSTEM_PROMPT = """You are a career writing assistant for Curatyn.

Given a structured job description and a candidate's CV text, write a
concise, specific cover letter and a short application email body. Return
ONLY valid JSON, no markdown fences, matching this exact shape:

{
  "coverLetter": string,
  "emailSubject": string,
  "emailBody": string
}

Rules:
- The cover letter must be 250 to 400 words, three to four paragraphs, and
  must reference at least two concrete details from the job description and
  at least one concrete detail from the candidate's CV. Never invent
  experience, employers, dates, or skills not present in the CV text.
- Match the tone described in "toneHints". Default to professional and
  warm if no hint is given.
- emailSubject should follow the pattern "Application for {roleTitle}".
- emailBody is a short covering note distinct from the full cover letter,
  two to four sentences, inviting the reader to review the attachments.
- End emailBody with "Best regards," on its own line; never invent a name.
"""


async def generate_cover_letter_and_email(
    structured_jd: dict,
    cv_raw_text: str,
    existing_subject: str | None,
    existing_body: str | None,
) -> dict:
    """existing_subject/body let the caller keep a user's manual edit instead
    of the freshly generated value — see app/routers/application_routes.py,
    which is the actual enforcement point for FR-REVIEW-004."""
    user_prompt = json.dumps({"jobDescription": structured_jd, "candidateCvText": cv_raw_text[:6000]})
    completion = await ai_client.complete(system=COVER_LETTER_SYSTEM_PROMPT, user=user_prompt)
    generated = json.loads(completion)

    return {
        "coverLetter": generated["coverLetter"],
        "emailSubject": existing_subject or generated["emailSubject"],
        "emailBody": existing_body or generated["emailBody"],
    }
