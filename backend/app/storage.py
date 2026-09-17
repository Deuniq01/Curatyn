"""
Object storage abstraction. Local disk in dev (STORAGE_DIR), swap the two
functions below for S3/Supabase Storage calls in production — nothing else
in the codebase needs to change, since every caller only ever sees a
`file_url` string and calls fetch_cv_pdf_bytes() / save_file() from here.
"""
import os
import uuid

from app.config import settings

os.makedirs(settings.storage_dir, exist_ok=True)


async def save_file(content: bytes, suggested_name: str) -> str:
    key = f"{uuid.uuid4()}-{suggested_name}"
    path = os.path.join(settings.storage_dir, key)
    with open(path, "wb") as f:
        f.write(content)
    return path  # in prod this would be an s3:// or https:// URL, not a local path


async def fetch_cv_pdf_bytes(file_url: str) -> bytes:
    with open(file_url, "rb") as f:
        return f.read()
