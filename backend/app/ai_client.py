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
import asyncio
import json
import re

import httpx

from app.config import settings
from app.models import EMBEDDING_DIM

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE_GEMINI_STATUSES = {429, 500, 502, 503, 504}


async def gemini_post(url: str, api_key: str, body: dict, timeout: float) -> httpx.Response:
    """Retry transient provider capacity/rate-limit failures, not config errors."""
    delays = (1, 2, 4)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(len(delays) + 1):
            response = await client.post(url, headers={"x-goog-api-key": api_key}, json=body)
            if response.status_code not in _RETRYABLE_GEMINI_STATUSES or attempt == len(delays):
                return response
            retry_after = response.headers.get("Retry-After")
            delay = min(float(retry_after), 10) if retry_after else delays[attempt]
            await asyncio.sleep(delay)
    raise RuntimeError("Gemini request retry loop ended unexpectedly")


class AIClient:
    async def complete(self, system: str, user: str) -> str:
        if settings.ai_backend == "mock":
            return _mock_complete(system, user)
        if settings.ai_backend == "gemini":
            return await _gemini_complete(system, user)
        raise NotImplementedError(
            f"AI_BACKEND={settings.ai_backend!r} is not wired up yet. "
            "Implement the Ollama HTTP call here, keeping the same "
            "(system, user) -> str signature."
        )

    async def embed(self, text: str) -> list[float]:
        if settings.ai_backend == "mock":
            return _mock_embed(text)
        if settings.ai_backend == "gemini":
            return await _gemini_embed(text)
        raise NotImplementedError(
            f"AI_BACKEND={settings.ai_backend!r} is not wired up yet. "
            "Implement the Ollama embedding call here, keeping the "
            f"same text -> list[float] of length {EMBEDDING_DIM} signature."
        )


ai_client = AIClient()


# ---------------------------------------------------------------------------
# Gemini backend (Google Generative Language API, plain REST over httpx)
# ---------------------------------------------------------------------------

def _require_api_key() -> str:
    if not settings.google_api_key:
        raise RuntimeError(
            "AI_BACKEND=gemini but GOOGLE_API_KEY is not set. Create a key at "
            "https://aistudio.google.com/apikey and set GOOGLE_API_KEY."
        )
    return settings.google_api_key


def _strip_code_fences(text: str) -> str:
    """Defensive: some completions wrap JSON in ```json ... ``` fences even
    when application/json is requested. ai_pipeline.py then json.loads() this."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped)
    return stripped.strip()


async def _gemini_complete(system: str, user: str) -> str:
    api_key = _require_api_key()
    url = f"{GEMINI_API_BASE}/models/{settings.gemini_model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        # Both Curatyn prompts demand strict JSON back; ask the model for it.
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }
    response = await gemini_post(url, api_key, body, timeout=60)
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini completion failed: {response.status_code} {response.text}")

    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        # e.g. blocked by safety filters, or empty candidate list.
        raise RuntimeError(f"Gemini returned no usable completion: {json.dumps(data)[:500]}") from exc
    return _strip_code_fences(text)


async def _gemini_embed(text: str) -> list[float]:
    api_key = _require_api_key()
    url = f"{GEMINI_API_BASE}/models/{settings.gemini_embed_model}:embedContent"
    body = {
        "model": f"models/{settings.gemini_embed_model}",
        "content": {"parts": [{"text": text or "empty"}]},
        "outputDimensionality": EMBEDDING_DIM,
    }
    response = await gemini_post(url, api_key, body, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini embedding failed: {response.status_code} {response.text}")

    values = response.json().get("embedding", {}).get("values")
    if not values:
        raise RuntimeError(f"Gemini embedding response missing values: {response.text[:500]}")
    if len(values) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Gemini embedding dimension {len(values)} != EMBEDDING_DIM {EMBEDDING_DIM}. "
            f"Set gemini_embed_model to a {EMBEDDING_DIM}-dim model (e.g. text-embedding-004) "
            "or update EMBEDDING_DIM in app/models.py and recreate the DB."
        )
    return values


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

    return json.dumps({
        "coverLetter": cover_letter,
        "emailSubject": email_subject,
    })
