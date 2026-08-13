"""GeoMate — FastAPI application entry point (Android-compatible).

Same API surface as the original backend. Runs embedded on Android via
Chaquopy or standalone on desktop via run.py.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db

# Import models so SQLAlchemy Base knows about them before create_all
import app.models.knowledge   # noqa: F401
import app.models.route       # noqa: F401
import app.models.user        # noqa: F401
import app.models.study_plan  # noqa: F401
import app.models.field_note  # noqa: F401
import app.models.document   # noqa: F401

# Pre-load light vector store module (replaces ChromaDB on Android)
import app.ai.rag.store  # noqa: F401  # ensures LightVectorStore is importable


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: create tables
    init_db()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — allow localhost origins (Android WebView connects via localhost)
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# Serve uploaded files (photos, etc.)
uploads_dir = settings.UPLOAD_DIR
Path(uploads_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Import and register API routers
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.routes import router as routes_router
from app.api.v1.study_plans import router as study_plans_router
from app.api.v1.field_notes import router as field_notes_router
from app.api.v1.documents import router as documents_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.users import router as users_router
from app.api.v1.upload import router as upload_router

app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
app.include_router(study_plans_router, prefix="/api/v1")
app.include_router(field_notes_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
