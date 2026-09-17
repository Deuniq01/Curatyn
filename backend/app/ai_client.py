"""
Thin AI client interface. app/ai_pipeline.py only ever calls
ai_client.complete(system, user) and ai_client.embed(text); it never knows
which backend is behind them.

AI_BACKEND=mock (the default) makes the entire application runnable and
testable with zero external API keys: complete() applies simple, honest
heuristics to the input instead of calling a model, and embed() produces a
deterministic pseudo-embedding from a text hash, which is enough to
demonstrate real pgvector cosine-similarity ranking end to end (closely
related CV/JD text hashes to similar vectors is NOT guaranteed the way a
real embedding model's semantic space is, so treat mock-mode match scores
as plumbing verification only, not as a stand-in for real matching
quality).

Switch AI_BACKEND to "gemini" and provide GOOGLE_API_KEY (add that setting
in app/config.py) to call the real Gemini API instead. The complete() and
embed() signatures do not need to change.
"""
import hashlib
import json
import re

from app.config import settings
from app.models import EMBEDDING_DIM


class AIClient:
    async def complete(self, system: str, user: str) -> str:
        if settings.ai_backend == "mock":
            return _mock_complete(system, user)
        raise NotImplementedError(
            f"AI_BACKEND={settings.ai_backend!r} is not wired up yet. "
            "Implement the Gemini/Ollama HTTP call here, keeping the same "
            "(system, user) -> str signature."
        )

    async def embed(self, text: str) -> list[float]:
        if settings.ai_backend == "mock":
            return _mock_embed(text)
        raise NotImplementedError(
            f"AI_BACKEND={settings.ai_backend!r} is not wired up yet. "
            "Implement the Gemini/Ollama embedding call here, keeping the "
            f"same text -> list[float] of length {EMBEDDING_DIM} signature."
        )


ai_client = AIClient()


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------

def _mock_embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding: hash overlapping word shingles into a
    fixed-length vector, then L2-normalize. Two texts that share more words
    land closer together in cosine distance than two that share none, which
    is enough to prove the pgvector query and ranking machinery works."""
    vec = [0.0] * EMBEDDING_DIM
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        words = ["empty"]
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        vec[0] = 1.0
        norm = 1.0
    return [v / norm for v in vec]


def _mock_complete(system: str, user: str) -> str:
    if "companyName" in system and "requiredSkills" in system:
        return _mock_jd_extraction(user)
    if "coverLetter" in system and "emailSubject" in system:
        return _mock_cover_letter(user)
    raise NotImplementedError("Mock AI backend does not recognize this prompt shape.")


def _mock_jd_extraction(raw_text: str) -> str:
    company_match = (
        re.search(r"(?:at|company:?)\s+([A-Z][A-Za-z0-9&.,'\- ]{2,40})", raw_text)
        or re.search(r"^([A-Z][A-Za-z0-9&.,'\- ]{2,40}?)\s+is\s+(?:hiring|looking|seeking)", raw_text)
    )
    role_match = re.search(
        r"(?:hiring|role:?|position:?|seeking (?:a|an))\s+([A-Za-z][A-Za-z0-9/&+ ]{2,50})",
        raw_text,
        re.IGNORECASE,
    )
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
    application_email = email_match.group(0).rstrip(".,;:") if email_match else None

    skill_vocab = [
        "python", "javascript", "typescript", "react", "next.js", "fastapi",
        "postgresql", "sql", "aws", "docker", "kubernetes", "graphql",
        "node.js", "django", "flask", "communication", "leadership",
    ]
    lowered = raw_text.lower()
    found_skills = [s for s in skill_vocab if s in lowered]

    payload = {
        "companyName": company_match.group(1).strip() if company_match else None,
        "roleTitle": role_match.group(1).strip() if role_match else None,
        "location": None,
        "seniorityLevel": None,
        "requiredSkills": found_skills[:5],
        "preferredSkills": found_skills[5:8],
        "responsibilities": [],
        "keyQualifications": [],
        "applicationEmail": application_email,
        "toneHints": "professional",
    }
    return json.dumps(payload)


def _mock_cover_letter(user_payload_json: str) -> str:
    payload = json.loads(user_payload_json)
    jd = payload.get("jobDescription", {})
    role = jd.get("roleTitle") or "this role"
    company = jd.get("companyName") or "your company"
    skills = jd.get("requiredSkills") or []
    skills_line = ", ".join(skills[:3]) if skills else "the skills outlined in the posting"

    cv_text = payload.get("candidateCvText", "")
    cv_snippet = cv_text.strip().splitlines()[0][:120] if cv_text.strip() else "my recent experience"

    cover_letter = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to apply for {role} at {company}. Your posting's emphasis on "
        f"{skills_line} lines up closely with my background, and I was glad to see "
        f"the role described the way it is.\n\n"
        f"In my most recent work, {cv_snippet}, which I believe translates directly "
        f"into the responsibilities this position calls for. I would welcome the "
        f"chance to bring that experience to your team.\n\n"
        f"Thank you for considering my application. I have attached my CV and would "
        f"be glad to discuss how I can contribute to {company}.\n\n"
        f"Sincerely,"
    )

    email_subject = f"Application for {role}" if role != "this role" else "Job Application"
    email_body = (
        f"Hello,\n\nPlease find attached my CV and cover letter for {role}. "
        f"I would appreciate the opportunity to discuss my application further.\n\n"
        f"Best regards,"
    )

    return json.dumps({
        "coverLetter": cover_letter,
        "emailSubject": email_subject,
        "emailBody": email_body,
    })
