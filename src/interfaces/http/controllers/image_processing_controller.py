"""Image processing controller - Individual endpoints for each operation.

Handles:
- Background removal (AI-powered with rembg)
- Watermarking (text and logo)
- Compression (3 levels: low, balanced, strong)

Each operation is independent and can be applied to already uploaded files.

File Upload Flow:
- Files <10MB: Direct upload via POST /api/v1/upload/{job_id}/file
- Files >10MB: Chunked upload from frontend
"""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import (
    ValidationError,
    JobNotFoundError,
)
from src.application.commands import ProcessImageCommand
from src.application.handlers import ProcessImageHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Image Processing"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================


class RemoveBackgroundRequest(BaseModel):
    """Request to remove background from image."""

    job_id: str = Field(..., description="Job identifier from upload")
    output_format: str = Field(
        "png", description="Output format (png recommended for transparency)"
    )
    model: str = Field(
        "u2net",
        description="AI model: u2net (general), u2netp (lightweight), u2net_human_seg (people), isnet-general-use, isnet-anime",
    )
    alpha_matting: bool = Field(
        False, description="Enable alpha matting for smoother edges (slower)"
    )
    strip_metadata: bool = Field(True, description="Remove EXIF data for privacy")


class CompressImageRequest(BaseModel):
    """Request to compress image."""

    job_id: str = Field(..., description="Job identifier from upload")
    output_format: str = Field(..., description="Output format: jpg, png, webp")
    level: str = Field(
        "balanced",
        description="Compression level: low (10-20%), balanced (30-60%), strong (60-90%)",
    )
    quality: int | None = Field(
        None, ge=0, le=100, description="Quality override (0-100, lower = smaller file)"
    )
    strip_metadata: bool = Field(True, description="Remove EXIF data for privacy")


class WatermarkImageRequest(BaseModel):
    """Request to add watermark to image."""

    job_id: str = Field(..., description="Job identifier from upload")
    output_format: str = Field(..., description="Output format: jpg, png, webp")
    type: str = Field(..., description="Watermark type: text or logo")

    # Text watermark params
    text: str | None = Field(None, description="Text content (required if type=text)")
    font_size: int = Field(40, description="Font size in pixels")
    color: str = Field("white", description="Text color (white, black, red, etc.)")

    # Logo watermark params
    logo_path: str | None = Field(
        None, description="Server path to logo PNG (required if type=logo)"
    )
    size_percent: int = Field(
        15, ge=1, le=50, description="Logo size as % of image width"
    )

    # Common params
    position: str = Field(
        "bottom-right",
        description="Position: top-left, top-right, center, bottom-left, bottom-right, diagonal",
    )
    opacity: float = Field(
        0.7, ge=0.0, le=1.0, description="Opacity (0.0 = transparent, 1.0 = opaque)"
    )
    margin: int = Field(20, description="Margin from edge in pixels")
    strip_metadata: bool = Field(True, description="Remove EXIF data for privacy")


class ProcessResponse(BaseModel):
    """Response for image processing operations."""

    job_id: str
    status: str
    message: str
    operation: str


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/remove-background",
    response_model=ProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Remove background from image",
    description="""
    Remove image background using AI-powered segmentation (rembg).
    
    **100% local processing** - No external APIs, privacy guaranteed.
    
    **File Upload Flow:**
    1. Upload file: POST /api/v1/upload/create → get job_id
    2. If <10MB: POST /api/v1/upload/{job_id}/file (single request)
    3. If >10MB: Use chunked upload from frontend
    4. Call this endpoint with job_id
    5. Download result: GET /api/v1/jobs/{job_id}/download
    
    **Models:**
    - `u2net`: General purpose (recommended)
    - `u2netp`: Lightweight, faster
    - `u2net_human_seg`: Optimized for people
    - `isnet-general-use`: High quality general
    - `isnet-anime`: Anime/illustration focused
    
    **Example:**
    ```json
    {
      "job_id": "abc123-def456",
      "output_format": "png",
      "model": "u2net",
      "alpha_matting": false
    }
    ```
    """,
)
async def remove_background(
    request: RemoveBackgroundRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessResponse:
    """Remove background from image using AI."""
    try:
        command = ProcessImageCommand(
            job_id=request.job_id,
            output_format=request.output_format,
            remove_background=True,
            background_model=request.model,
            alpha_matting=request.alpha_matting,
            compress_enabled=False,
            watermark_enabled=False,
            strip_metadata=request.strip_metadata,
        )

        handler = ProcessImageHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Background removal queued successfully. Processing will start shortly.",
            operation="remove_background",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Background removal failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing background: {e}", exc_info=True)
        raise


@router.post(
    "/compress",
    response_model=ProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Compress image",
    description="""
    Compress image to reduce file size while maintaining quality.
    
    **Compression Levels:**
    - `low`: 10-20% reduction (jpegoptim, oxipng lossless)
    - `balanced`: 30-60% reduction ⭐ **Recommended** (mozjpeg, pngquant)
    - `strong`: 60-90% reduction (mozjpeg aggressive, pngquant strong)
    
    **Tools Used:**
    - JPEG: jpegoptim (low), mozjpeg (balanced/strong)
    - PNG: oxipng (low), pngquant (balanced/strong)
    - WebP: cwebp with quality settings
    
    **File Upload Flow:**
    1. Upload file: POST /api/v1/upload/create → get job_id
    2. If <10MB: POST /api/v1/upload/{job_id}/file (single request)
    3. If >10MB: Use chunked upload from frontend
    4. Call this endpoint with job_id
    5. Download result: GET /api/v1/jobs/{job_id}/download
    
    **Example:**
    ```json
    {
      "job_id": "abc123-def456",
      "output_format": "jpg",
      "level": "balanced",
      "quality": 80
    }
    ```
    """,
)
async def compress_image(
    request: CompressImageRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessResponse:
    """Compress image with smart quality optimization."""
    try:
        command = ProcessImageCommand(
            job_id=request.job_id,
            output_format=request.output_format,
            remove_background=False,
            compress_enabled=True,
            compression_level=request.level,
            compression_quality=request.quality,
            watermark_enabled=False,
            strip_metadata=request.strip_metadata,
        )

        handler = ProcessImageHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=f"Image compression ({request.level}) queued successfully.",
            operation="compress",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Compression failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error compressing image: {e}", exc_info=True)
        raise


@router.post(
    "/watermark",
    response_model=ProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add watermark to image",
    description="""
    Add text or logo watermark to protect your images.
    
    **Watermark Types:**
    - `text`: Custom text with font, color, size
    - `logo`: PNG logo with transparency support
    
    **Positions:**
    - `top-left`, `top-right`: Corner positions
    - `center`: Dead center
    - `bottom-left`, `bottom-right`: Bottom corners
    - `diagonal`: Rotated 45° across image
    
    **File Upload Flow:**
    1. Upload file: POST /api/v1/upload/create → get job_id
    2. If <10MB: POST /api/v1/upload/{job_id}/file (single request)
    3. If >10MB: Use chunked upload from frontend
    4. Call this endpoint with job_id
    5. Download result: GET /api/v1/jobs/{job_id}/download
    
    **Example (Text):**
    ```json
    {
      "job_id": "abc123-def456",
      "output_format": "jpg",
      "type": "text",
      "text": "© 2026 MyBrand",
      "position": "bottom-right",
      "opacity": 0.7,
      "font_size": 40,
      "color": "white"
    }
    ```
    
    **Example (Logo):**
    ```json
    {
      "job_id": "abc123-def456",
      "output_format": "png",
      "type": "logo",
      "logo_path": "/path/to/logo.png",
      "position": "top-right",
      "opacity": 0.8,
      "size_percent": 15
    }
    ```
    """,
)
async def add_watermark(
    request: WatermarkImageRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessResponse:
    """Add watermark (text or logo) to image."""
    try:
        # Validate type-specific params
        if request.type == "text" and not request.text:
            raise ValidationError("'text' field is required when type='text'")
        if request.type == "logo" and not request.logo_path:
            raise ValidationError("'logo_path' field is required when type='logo'")

        watermark_params = {
            "text": request.text,
            "logo_path": request.logo_path,
            "position": request.position,
            "opacity": request.opacity,
            "font_size": request.font_size,
            "color": request.color,
            "margin": request.margin,
            "size_percent": request.size_percent,
        }

        command = ProcessImageCommand(
            job_id=request.job_id,
            output_format=request.output_format,
            remove_background=False,
            compress_enabled=False,
            watermark_enabled=True,
            watermark_type=request.type,
            watermark_params=watermark_params,
            strip_metadata=request.strip_metadata,
        )

        handler = ProcessImageHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=f"Watermark ({request.type}) queued successfully.",
            operation="watermark",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Watermark failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding watermark: {e}", exc_info=True)
        raise
