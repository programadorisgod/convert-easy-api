"""Image-to-PDF controller.

Combines one or more uploaded images into a single multi-page PDF. The
primary job becomes page 1 and each additional image (source_job_ids)
becomes a subsequent page, in the order provided by the client.
"""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import ProcessImageToPdfCommand
from src.application.handlers import ProcessImageToPdfHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process/image", tags=["Image Processing"])


class ImageToPdfRequest(BaseModel):
    """Request to combine images into a single PDF."""

    job_id: str = Field(..., description="Image job identifier (becomes page 1)")
    source_job_ids: list[str] = Field(
        default_factory=list,
        description="Additional image job identifiers for the remaining pages, in order",
    )


class ImageToPdfResponse(BaseModel):
    """Response for image-to-PDF conversion."""

    job_id: str
    status: str
    message: str
    operation: str
    page_count: int


@router.post(
    "/to-pdf",
    response_model=ImageToPdfResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Combine images into a single PDF",
    description="""
    Combine one or more uploaded images into a single multi-page PDF.

    Each image becomes one full page. The primary job becomes page 1; the
    images in `source_job_ids` become the following pages in the given order.

    **File Upload Flow:**
    1. Create + upload one job per image: POST /api/v1/upload/create + upload file
    2. Pick the first image as `job_id` and the rest as `source_job_ids` (in page order)
    3. Call this endpoint with the ordered job ids
    4. Download result: GET /api/v1/jobs/{job_id}/download

    **Example (3 images → PDF):**
    ```json
    {
      "job_id": "img-1",
      "source_job_ids": ["img-2", "img-3"]
    }
    ```
    """,
)
async def images_to_pdf(
    request: ImageToPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ImageToPdfResponse:
    try:
        command = ProcessImageToPdfCommand(
            job_id=request.job_id,
            source_job_ids=request.source_job_ids,
        )
        handler = ProcessImageToPdfHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ImageToPdfResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=(
                f"Image to PDF queued successfully with "
                f"{result['page_count']} page(s)."
            ),
            operation="image_to_pdf",
            page_count=result["page_count"],
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Image to PDF failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error converting images to PDF: {e}", exc_info=True)
        raise
