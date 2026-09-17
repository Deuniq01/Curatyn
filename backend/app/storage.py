"""
Object storage abstraction. Two backends, chosen by STORAGE_BACKEND:

  * "local"    — writes to STORAGE_DIR on local disk (dev only; ephemeral on
                 hosts like Render, so do NOT use in production).
  * "supabase" — stores objects in a PRIVATE Supabase Storage bucket via the
                 REST API using the service_role key. Nothing in the rest of
                 the codebase changes: every caller only ever sees the opaque
                 string returned by save_file() and passes it to
                 fetch_cv_pdf_bytes().
"""
import os
import uuid
from urllib.parse import quote

import httpx

from app.config import settings

_LOCAL = settings.storage_backend == "local"

if _LOCAL:
    os.makedirs(settings.storage_dir, exist_ok=True)


def _safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in name) or "file"


# ---------------------------------------------------------------------------
# Supabase Storage
# ---------------------------------------------------------------------------

def _supabase_headers() -> dict:
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "STORAGE_BACKEND=supabase but SUPABASE_URL / SUPABASE_SERVICE_KEY are not set."
        )
    return {"Authorization": f"Bearer {settings.supabase_service_key}"}


async def _supabase_save(content: bytes, key: str) -> str:
    base = settings.supabase_url.rstrip("/")
    url = f"{base}/storage/v1/object/{settings.storage_bucket}/{quote(key, safe='')}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={**_supabase_headers(), "Content-Type": "application/pdf", "x-upsert": "true"},
            content=content,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase upload failed: {response.status_code} {response.text}")
    return key  # stored as file_url; bucket is implied by settings


async def _supabase_fetch(key: str) -> bytes:
    base = settings.supabase_url.rstrip("/")
    url = f"{base}/storage/v1/object/authenticated/{settings.storage_bucket}/{quote(key, safe='')}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url, headers=_supabase_headers())
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase download failed: {response.status_code} {response.text}")
    return response.content


# ---------------------------------------------------------------------------
# Public API (backend-agnostic)
# ---------------------------------------------------------------------------

async def save_file(content: bytes, suggested_name: str) -> str:
    key = f"{uuid.uuid4()}-{_safe_name(suggested_name)}"
    if _LOCAL:
        path = os.path.join(settings.storage_dir, key)
        with open(path, "wb") as f:
            f.write(content)
        return path
    return await _supabase_save(content, key)


async def fetch_cv_pdf_bytes(file_url: str) -> bytes:
    if _LOCAL:
        with open(file_url, "rb") as f:
            return f.read()
    return await _supabase_fetch(file_url)
