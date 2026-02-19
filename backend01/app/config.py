"""
PharmaGuard Configuration — loads environment variables via pydantic-settings.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # ── API Keys ──────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "pharmaguard-pgx")

    # ── App ───────────────────────────────────────────────────
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() == "true"

    # ── Constraints ───────────────────────────────────────────
    MAX_VCF_SIZE_MB: int = 5
    SUPPORTED_VCF_VERSION: str = "VCFv4.2"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
