import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.api.v1.router import v1_router
from app.api.v1.schemas import HealthResponse
from app.core.config import settings
from app.core.logging import logger
from app.database.session import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database and prepare resources."""
    logger.info("Initializing Rural AI Medical Helpline...")
    init_db()
    logger.info(f"Helpline service started in {settings.ENVIRONMENT} mode.")
    yield
    logger.info("Shutting down Rural AI Medical Helpline...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Independent, hackathon-ready multilingual medical helpline for rural feature phones. "
        "Supports English, Hindi, and Marathi via telephone keypad (DTMF) and spoken symptom triage."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for local dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler - prevents internal stack trace leaks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", exc_info=settings.DEBUG)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred while processing the helpline request.",
            "status_code": 500,
        },
    )


# Mount static assets
static_dir = os.path.join(os.path.dirname(__file__), "dashboard", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Service health check endpoint verifying database connectivity."""
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        service="rural-medical-helpline",
        version=settings.APP_VERSION,
        database=db_status,
        timestamp=datetime.utcnow().isoformat(),
        telephony_provider=settings.TELEPHONY_PROVIDER,
    )


@app.get("/", include_in_schema=False)
async def root_dashboard():
    """Serve the web dashboard and interactive feature phone simulator."""
    template_path = os.path.join(os.path.dirname(__file__), "dashboard", "templates", "index.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return {
        "message": "Rural AI Medical Helpline API is running.",
        "docs": "/docs",
        "health": "/health",
    }


# Include API v1 router
app.include_router(v1_router)
