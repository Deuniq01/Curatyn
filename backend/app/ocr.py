"""Extract job-posting text from screenshots using Gemini vision."""
import base64

import httpx

from app.ai_client import GEMINI_API_BASE, gemini_post
from app.config import settings


async def extract_text_from_image(content: bytes, mime_type: str) -> str:
    if settings.ai_backend != "gemini":
        raise RuntimeError("Image job analysis requires AI_BACKEND=gemini.")
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured for image job analysis.")

    url = f"{GEMINI_API_BASE}/models/{settings.gemini_model}:generateContent"
    body = {
        "contents": [{"parts": [
            {"text": "Transcribe this job posting image exactly as readable plain text. Return only the transcription."},
            {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(content).decode("ascii")}},
        ]}],
    }
    response = await gemini_post(url, settings.google_api_key, body, timeout=90)
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini image transcription failed: {response.status_code} {response.text}")
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned no readable text for this image.") from exc
