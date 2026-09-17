"""
Central settings. AI_BACKEND and EMAIL_BACKEND default to "mock" so the
whole application is runnable and testable without real Gemini/Ollama or
Gmail/Microsoft credentials. Set them to "gemini" and "live" respectively
(and provide the matching credentials below) once real keys exist — see
DEPLOYMENT.md.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://curatyn:curatyn@localhost:5432/curatyn"
    database_ssl_verify: bool = True
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    curatyn_token_encryption_key: str = ""

    # --- AI --------------------------------------------------------------
    ai_backend: str = "mock"  # "mock" | "gemini" | "ollama"
    google_api_key: str = ""  # Gemini API key from Google AI Studio (aistudio.google.com)
    gemini_model: str = "gemini-2.0-flash"          # used by complete()
    gemini_embed_model: str = "text-embedding-004"  # 768-dim, matches models.EMBEDDING_DIM

    # --- Email -----------------------------------------------------------
    email_backend: str = "mock"  # "mock" | "live" — mock never calls Gmail/Graph, records sends in memory/db only

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/oauth/gmail/callback"

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/api/auth/oauth/outlook/callback"

    # --- Storage ---------------------------------------------------------
    storage_backend: str = "local"  # "local" | "supabase"
    storage_dir: str = "./local_storage"  # used when storage_backend=local
    supabase_url: str = ""          # e.g. https://xxxx.supabase.co
    supabase_service_key: str = ""  # service_role key — server-side only, never sent to the frontend
    storage_bucket: str = "cvs"     # a PRIVATE Supabase Storage bucket

    # --- Web / CORS ------------------------------------------------------
    # Where the browser app runs; used for the post-OAuth redirect back.
    frontend_url: str = "http://localhost:3000"
    # Comma-separated list of origins allowed to call this API from a browser.
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
