"""Document processing controller (Phase 2)."""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import ProcessDocumentCommand
from src.application.handlers import ProcessDocumentHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Document Processing"])


class ProcessDocumentRequest(BaseModel):
    """Request to convert uploaded document."""

    job_id: str = Field(..., description="Job identifier from upload workflow")
    output_format: str = Field(..., description="Target format (pdf, docx, html, etc.)")
    preferred_engine: str = Field(
        "auto",
        description="Engine selection: auto, pandoc, libreoffice",
    )


class ProcessDocumentResponse(BaseModel):
    """Response for document processing operation."""

    job_id: str
    status: str
    message: str
    document_config: dict


@router.post(
    "/document",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process document conversion",
    description="Queue a document conversion job using auto engine selection or explicit engine preference.",
)
async def process_document(
    request: ProcessDocumentRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessDocumentResponse:
    """Queue Phase 2 document conversion for an uploaded file."""
    try:
        command = ProcessDocumentCommand(
            job_id=request.job_id,
            output_format=request.output_format.lower(),
            preferred_engine=request.preferred_engine.lower(),
        )

        handler = ProcessDocumentHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessDocumentResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Document conversion queued successfully.",
            document_config=result["document_config"],
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Document processing failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing document: {e}", exc_info=True)
        raise
