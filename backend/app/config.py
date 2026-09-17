"""
Central settings. AI_BACKEND and EMAIL_BACKEND default to "mock" so the
whole application is runnable and testable without real Gemini/Ollama or
Gmail/Microsoft credentials. Set them to "gemini"/"ollama" and
"gmail"/"outlook" respectively (per user, at the account level, not
globally — see models.User.email_provider) once real credentials exist.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://curatyn:curatyn@localhost:5432/curatyn"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    curatyn_token_encryption_key: str = ""

    ai_backend: str = "mock"  # "mock" | "gemini" | "ollama"
    email_backend: str = "mock"  # "mock" | "live" — mock never calls Gmail/Graph, records sends in memory/db only

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/oauth/gmail/callback"

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/api/auth/oauth/outlook/callback"

    storage_dir: str = "./local_storage"

    class Config:
        env_file = ".env"


settings = Settings()
