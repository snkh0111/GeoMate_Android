"""Application configuration loaded from environment variables.
Android-Adapted: uses Android app data directory when running on Android.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend root
load_dotenv()


def _get_base_dir() -> Path:
    """Resolve base directory: Android app-private data dir or filesystem path."""
    # Chaquopy sets these on Android
    android_data = os.environ.get("ANDROID_APP_DATA_DIR")
    if android_data:
        return Path(android_data)
    # Fallback: relative to this file
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
DATA_DIR = BASE_DIR / "data"


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "GeoMate")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.1")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Database — SQLite file under data/
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR}/geomate.db"
    )

    # Vector Store — LightVectorStore (SQLite-backed, replaces ChromaDB on Android)
    LIGHT_VECTOR_DB_PATH: str = os.getenv(
        "LIGHT_VECTOR_DB_PATH", str(DATA_DIR / "vectors.db")
    )

    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # CORS — allow localhost (Android WebView connects via localhost)
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    )

    # Upload
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads"))

    # Server (for embedded Android use)
    SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))


settings = Settings()

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
