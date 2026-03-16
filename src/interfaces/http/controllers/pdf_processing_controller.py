"""PDF processing controller."""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import ProcessPdfCommand
from src.application.handlers import ProcessPdfHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process/pdf", tags=["PDF Processing"])


class PdfProcessResponse(BaseModel):
    """Response for PDF processing operations."""

    job_id: str
    status: str
    message: str
    operation: str
    pdf_config: dict


class MergePdfRequest(BaseModel):
    job_id: str = Field(..., description="Primary PDF job identifier")
    source_job_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Additional PDF job identifiers to merge after the primary PDF",
    )


class PageNumbersRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    page_numbers: list[int] = Field(
        ...,
        min_length=1,
        description="1-based page numbers",
    )


class RotatePdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    rotation: int = Field(..., description="Rotation in degrees, multiple of 90")
    page_numbers: list[int] | None = Field(
        None,
        description="Optional 1-based page numbers. Omit to rotate all pages.",
    )


class UpdateMetadataRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    metadata: dict[str, str] = Field(
        ...,
        description="Metadata key/value pairs, e.g. Title, Author, Subject",
    )


class EncryptPdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    user_password: str = Field(
        ..., min_length=1, description="Password for opening the PDF"
    )
    owner_password: str | None = Field(
        None,
        description="Optional owner password for permissions control",
    )


class DecryptPdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    password: str = Field(..., min_length=1, description="Current PDF password")


class AddTextPdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    page_number: int = Field(..., ge=1, description="1-based page number")
    text: str = Field(..., min_length=1, description="Text to insert")
    x: float = Field(..., description="Horizontal position in PDF points")
    y: float = Field(..., description="Vertical position in PDF points")
    font_size: int = Field(12, gt=0, description="Font size in points")
    color: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="RGB values normalized between 0 and 1",
    )


class AddImagePdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    image_job_id: str = Field(..., description="Uploaded image job identifier")
    page_number: int = Field(..., ge=1, description="1-based page number")
    x0: float = Field(...)
    y0: float = Field(...)
    x1: float = Field(...)
    y1: float = Field(...)


class DrawRectanglePdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    page_number: int = Field(..., ge=1, description="1-based page number")
    x0: float = Field(...)
    y0: float = Field(...)
    x1: float = Field(...)
    y1: float = Field(...)
    color: list[float] = Field(
        default_factory=lambda: [1.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="Stroke RGB values normalized between 0 and 1",
    )
    fill_color: list[float] | None = Field(
        None,
        min_length=3,
        max_length=3,
        description="Optional fill RGB values normalized between 0 and 1",
    )
    width: float = Field(1.0, gt=0, description="Stroke width")


class AddAnnotationPdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    page_number: int = Field(..., ge=1, description="1-based page number")
    text: str = Field(..., min_length=1, description="Annotation content")
    x: float = Field(...)
    y: float = Field(...)


class SetMediaboxPdfRequest(BaseModel):
    job_id: str = Field(..., description="PDF job identifier")
    page_number: int = Field(..., ge=1, description="1-based page number")
    x0: float = Field(...)
    y0: float = Field(...)
    x1: float = Field(...)
    y1: float = Field(...)


async def _queue_pdf_operation(
    job_id: str,
    operation: str,
    operation_params: dict,
    source_job_ids: list[str] | None,
    repository: JobRepository,
    queue: BullMQAdapter,
    storage: FileStorage,
) -> PdfProcessResponse:
    command = ProcessPdfCommand(
        job_id=job_id,
        operation=operation,
        operation_params=operation_params,
        source_job_ids=source_job_ids or [],
    )

    handler = ProcessPdfHandler(repository, queue, storage)
    result = await handler.handle(command)

    return PdfProcessResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=f"PDF operation '{operation}' queued successfully.",
        operation=operation,
        pdf_config=result["pdf_config"],
    )


@router.post(
    "/merge",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Merge PDFs",
)
async def merge_pdfs(
    request: MergePdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    try:
        return await _queue_pdf_operation(
            job_id=request.job_id,
            operation="merge",
            operation_params={},
            source_job_ids=request.source_job_ids,
            repository=repository,
            queue=queue,
            storage=storage,
        )
    except (JobNotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error merging PDFs: {e}", exc_info=True)
        raise


@router.post(
    "/extract-pages",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract pages into a new PDF",
)
async def extract_pages(
    request: PageNumbersRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="extract_pages",
        operation_params={"page_numbers": request.page_numbers},
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/delete-pages",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete selected pages",
)
async def delete_pages(
    request: PageNumbersRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="delete_pages",
        operation_params={"page_numbers": request.page_numbers},
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/rotate",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rotate PDF pages",
)
async def rotate_pages(
    request: RotatePdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="rotate_pages",
        operation_params={
            "rotation": request.rotation,
            "page_numbers": request.page_numbers,
        },
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/metadata",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update PDF metadata",
)
async def update_metadata(
    request: UpdateMetadataRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="update_metadata",
        operation_params={"metadata": request.metadata},
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/encrypt",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encrypt PDF",
)
async def encrypt_pdf(
    request: EncryptPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="encrypt",
        operation_params={
            "user_password": request.user_password,
            "owner_password": request.owner_password,
        },
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/decrypt",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Decrypt PDF",
)
async def decrypt_pdf(
    request: DecryptPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="decrypt",
        operation_params={"password": request.password},
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/add-text",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Insert text into a PDF page",
)
async def add_text(
    request: AddTextPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="add_text",
        operation_params=request.model_dump(exclude={"job_id"}),
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/add-image",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Insert an image into a PDF page",
)
async def add_image(
    request: AddImagePdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="add_image",
        operation_params=request.model_dump(exclude={"job_id"}),
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/draw-rectangle",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Draw a rectangle on a PDF page",
)
async def draw_rectangle(
    request: DrawRectanglePdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="draw_rectangle",
        operation_params=request.model_dump(exclude={"job_id"}),
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/add-annotation",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a text annotation to a PDF page",
)
async def add_annotation(
    request: AddAnnotationPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="add_annotation",
        operation_params=request.model_dump(exclude={"job_id"}),
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )


@router.post(
    "/set-mediabox",
    response_model=PdfProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Adjust page mediabox/layout",
)
async def set_mediabox(
    request: SetMediaboxPdfRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> PdfProcessResponse:
    return await _queue_pdf_operation(
        job_id=request.job_id,
        operation="set_mediabox",
        operation_params=request.model_dump(exclude={"job_id"}),
        source_job_ids=None,
        repository=repository,
        queue=queue,
        storage=storage,
    )
