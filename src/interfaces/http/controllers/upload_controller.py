"""Upload controller for file uploads and job creation.

Handles:
- Creating new conversion jobs
- Uploading file chunks
- Uploading complete files
- Starting conversion process
"""

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from shared.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileSizeLimitError,
    JobNotFoundError,
)
from src.application.commands import (
    CreateJobCommand,
    UploadChunkCommand,
    UploadCompleteFileCommand,
    MergeChunksCommand,
    StartConversionCommand,
)
from src.application.handlers import (
    CreateJobHandler,
    UploadChunkHandler,
    UploadCompleteFileHandler,
    MergeChunksHandler,
    StartConversionHandler,
)
from src.infrastructure.persistence import JobRepository
from src.infrastructure.storage.file_storage import FileStorage
from src.infrastructure.queue import BullMQAdapter
from src.lifespan import get_repository, get_storage, get_queue
from src.interfaces.http.schemas.upload import (
    CreateJobRequest,
    CreateJobResponse,
    UploadChunkResponse,
    MergeChunksResponse,
    StartConversionResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post(
    "/create",
    response_model=CreateJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new conversion job",
    description="Creates a new job for file conversion. Returns job_id and file_id for subsequent uploads.",
)
async def create_job(
    request: CreateJobRequest,
    repository: JobRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
) -> CreateJobResponse:
    """Create a new conversion job."""
    try:
        # Create command
        command = CreateJobCommand(
            input_format=request.input_format,
            output_formats=request.output_formats,
            original_size=request.original_size,
            total_chunks=request.total_chunks,
        )

        # Handle command
        handler = CreateJobHandler(repository, storage)
        job_id = await handler.handle(command)

        # Get job to return file_id
        job = await repository.get_job(job_id)

        return CreateJobResponse(
            job_id=job_id,
            file_id=job.file_id,
            status=job.status.value,
            message=f"Job created successfully. Upload {job.total_chunks} chunk(s).",
        )

    except (ValidationError, UnsupportedFormatError, FileSizeLimitError) as e:
        logger.warning(f"Job creation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating job: {e}", exc_info=True)
        raise


@router.post(
    "/{job_id}/chunk",
    response_model=UploadChunkResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload file chunk",
    description="Upload a single chunk for a multi-part upload. Use for files >10MB.",
)
async def upload_chunk(
    job_id: str,
    chunk_index: int = Form(..., description="Chunk index (0-based)"),
    chunk: UploadFile = File(..., description="Chunk data"),
    repository: JobRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
) -> UploadChunkResponse:
    """Upload a file chunk."""
    try:
        # Read chunk data
        chunk_data = await chunk.read()

        # Create command
        command = UploadChunkCommand(
            job_id=job_id,
            chunk_index=chunk_index,
            chunk_data=chunk_data,
        )

        # Handle command
        handler = UploadChunkHandler(repository, storage)
        result = await handler.handle(command)

        return UploadChunkResponse(
            job_id=result["job_id"],
            chunk_index=result["chunk_index"],
            chunks_uploaded=result["chunks_uploaded"],
            total_chunks=result["total_chunks"],
            is_complete=result["is_complete"],
            message=f"Chunk {chunk_index} uploaded successfully. "
            f"{result['chunks_uploaded']}/{result['total_chunks']} complete.",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Chunk upload failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading chunk: {e}", exc_info=True)
        raise


@router.post(
    "/{job_id}/file",
    response_model=UploadChunkResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload complete file",
    description="Upload a complete file (no chunking). Use for files <10MB.",
)
async def upload_file(
    job_id: str,
    file: UploadFile = File(..., description="Complete file data"),
    repository: JobRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
) -> UploadChunkResponse:
    """Upload a complete file."""
    try:
        # Read file data
        file_data = await file.read()

        # Create command
        command = UploadCompleteFileCommand(
            job_id=job_id,
            file_data=file_data,
        )

        # Handle command
        handler = UploadCompleteFileHandler(repository, storage)
        result = await handler.handle(command)

        return UploadChunkResponse(
            job_id=result["job_id"],
            chunk_index=0,
            chunks_uploaded=1,
            total_chunks=1,
            is_complete=True,
            message="File uploaded successfully.",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"File upload failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file: {e}", exc_info=True)
        raise


@router.post(
    "/{job_id}/merge",
    response_model=MergeChunksResponse,
    status_code=status.HTTP_200_OK,
    summary="Merge uploaded chunks",
    description="Merge all uploaded chunks into a single file. Required for multi-chunk uploads before starting conversion.",
)
async def merge_chunks(
    job_id: str,
    repository: JobRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
) -> MergeChunksResponse:
    """Merge uploaded chunks into single file."""
    try:
        # Create command
        command = MergeChunksCommand(job_id=job_id)

        # Handle command
        handler = MergeChunksHandler(repository, storage)
        result = await handler.handle(command)

        # Build response message
        if result["merged"]:
            message = (
                f"Successfully merged {result['total_chunks']} chunks "
                f"into single file ({result['file_size']} bytes). "
                f"Ready for conversion."
            )
        else:
            message = f"{result['reason']}. Ready for conversion."

        return MergeChunksResponse(
            job_id=result["job_id"],
            file_id=result["file_id"],
            merged=result["merged"],
            total_chunks=result.get("total_chunks"),
            file_size=result["file_size"],
            reason=result.get("reason"),
            message=message,
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Merge chunks failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error merging chunks: {e}", exc_info=True)
        raise


@router.post(
    "/{job_id}/start",
    response_model=StartConversionResponse,
    status_code=status.HTTP_200_OK,
    summary="Start conversion",
    description="Start the conversion process. All chunks must be uploaded and merged first.",
)
async def start_conversion(
    job_id: str,
    repository: JobRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
    queue: BullMQAdapter = Depends(get_queue),
) -> StartConversionResponse:
    """Start conversion process."""
    try:
        # Create command
        command = StartConversionCommand(job_id=job_id)

        # Handle command
        handler = StartConversionHandler(repository, storage, queue)
        result = await handler.handle(command)

        return StartConversionResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Conversion started. Job is being processed.",
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Start conversion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting conversion: {e}", exc_info=True)
        raise
