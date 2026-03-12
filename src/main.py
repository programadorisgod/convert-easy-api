"""FastAPI application entry point.

Following best practices:
- Clean dependency injection via Depends()
- Proper CORS configuration
- Structured logging
- API versioning with prefix
- OpenAPI documentation
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from src.interfaces.http.schemas.health import HealthResponse
from src.interfaces.http.schemas.root import RootResponse
from src.interfaces.http.exception_handlers import register_exception_handlers
from src.interfaces.http.controllers import (
    upload_controller,
    job_controller,
    websocket_controller,
    image_processing_controller,
)

from .lifespan import lifespan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


settings = get_settings()

# Log CORS configuration for debugging
logger.info(f"CORS Origins configured: {settings.cors_origins}")
logger.info(f"CORS Origins type: {type(settings.cors_origins)}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Privacy-focused file conversion API.

    Features

    * Image Conversion - Convert between 200+ image formats using ImageMagick
    * Chunked Uploads - Reliable uploads for large files (>10MB)
    * Real-time Updates - WebSocket notifications for job status
    * Privacy First - No persistent storage, immediate file deletion
    * Event Sourced - Complete audit trail of all operations

    Supported Formats (Phase 1 - Images)

    Input: JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, SVG

    Output: JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF

    Note: SVG output disabled for security reasons
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Permite todos los subdominios de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(upload_controller.router, prefix=settings.api_v1_prefix)
app.include_router(job_controller.router, prefix=settings.api_v1_prefix)
app.include_router(websocket_controller.router, prefix=settings.api_v1_prefix)
app.include_router(image_processing_controller.router, prefix=settings.api_v1_prefix)

logger.info(f"API routers registered with prefix: {settings.api_v1_prefix}")


@app.get("/health", tags=["Health"], response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
    )


@app.get("/", tags=["Root"], response_model=RootResponse)
async def root():
    return RootResponse(
        message="Easy Convert API - Privacy-focused file conversion",
        version=settings.app_version,
        docs="/docs",
        health="/health",
        api=settings.api_v1_prefix,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
