"""Job controller for job status and management.

Handles:
- Getting job status
- Cancelling jobs
- Downloading conversion results
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import CancelJobCommand, GetJobStatusCommand
from src.application.handlers import CancelJobHandler, GetJobStatusHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.storage.file_storage import FileStorage
from src.infrastructure.queue import BullMQAdapter
from src.lifespan import get_repository, get_storage, get_queue
from src.interfaces.http.schemas.upload import (
    JobStatusResponse,
    CancelJobRequest,
    CancelJobResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job status",
    description="Retrieve current status and details of a conversion job.",
)
async def get_job_status(
    job_id: str,
    repository: JobRepository = Depends(get_repository),
) -> JobStatusResponse:
    """Get job status."""
    try:
        # Create command
        command = GetJobStatusCommand(job_id=job_id)

        # Handle command
        handler = GetJobStatusHandler(repository)
        job_data = await handler.handle(command)

        return JobStatusResponse(**job_data)

    except JobNotFoundError as e:
        logger.warning(f"Job not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting job status: {e}", exc_info=True)
        raise


@router.post(
    "/{job_id}/cancel",
    response_model=CancelJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel job",
    description="Cancel a pending or processing job.",
)
async def cancel_job(
    job_id: str,
    request: CancelJobRequest | None = None,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
) -> CancelJobResponse:
    """Cancel a job."""
    try:
        # Create command
        command = CancelJobCommand(
            job_id=job_id,
            reason=request.reason if request else None,
        )

        # Handle command
        handler = CancelJobHandler(repository, queue)
        result = await handler.handle(command)

        return CancelJobResponse(
            job_id=result["job_id"],
            status=result["status"],
            message=f"Job cancelled: {result['reason']}",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Cancel job failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error cancelling job: {e}", exc_info=True)
        raise


@router.get(
    "/{job_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download conversion result",
    description="Download the converted file. File is deleted after download.",
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Converted file",
        }
    },
)
async def download_result(
    job_id: str,
    storage: FileStorage = Depends(get_storage),
    repository: JobRepository = Depends(get_repository),
) -> StreamingResponse:
    """Download conversion result."""
    try:
        # Verify job is completed
        job = await repository.get_job(job_id)

        if job.status.value != "completed":
            raise ValidationError(
                f"Job is not completed yet. Current status: {job.status.value}"
            )

        # Get output file path
        output_path = await storage.get_output(job.file_id)

        # Determine media type from output format
        output_format = job.output_format or "bin"
        media_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "ico": "image/x-icon",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "odt": "application/vnd.oasis.opendocument.text",
            "rtf": "application/rtf",
            "txt": "text/plain",
            "md": "text/markdown",
            "markdown": "text/markdown",
            "html": "text/html",
            "htm": "text/html",
            "epub": "application/epub+zip",
            "tex": "application/x-tex",
            "latex": "application/x-tex",
            "csv": "text/csv",
            "tsv": "text/tab-separated-values",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ods": "application/vnd.oasis.opendocument.spreadsheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "odp": "application/vnd.oasis.opendocument.presentation",
        }
        media_type = media_type_map.get(output_format, "application/octet-stream")

        # Stream file for download
        async def file_stream():
            async for chunk in storage.stream_file(output_path):
                yield chunk

            # Clean up files after download
            await storage.cleanup_file(job.file_id, include_output=True)
            logger.info(f"Cleaned up files for job {job_id} after download")

        return StreamingResponse(
            file_stream(),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="converted.{output_format}"',
                "Content-Length": str(output_path.stat().st_size),
            },
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Download failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading result: {e}", exc_info=True)
        raise
