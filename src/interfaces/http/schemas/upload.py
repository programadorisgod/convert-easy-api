"""Upload and conversion request/response schemas."""

from pydantic import BaseModel, Field, field_validator


class CreateJobRequest(BaseModel):
    """Request to create a new conversion job."""

    input_format: str = Field(
        ...,
        description="Input file format (e.g., 'png', 'jpg')",
        min_length=2,
        max_length=10,
    )
    output_formats: list[str] = Field(
        ...,
        description="List of desired output formats",
        min_length=1,
        max_length=5,
    )
    original_size: int = Field(
        ...,
        description="Original file size in bytes",
        gt=0,
    )
    total_chunks: int = Field(
        default=1,
        description="Number of chunks for upload (1 for complete file)",
        ge=1,
    )

    @field_validator("input_format", "output_formats")
    @classmethod
    def lowercase_formats(cls, v):
        """Convert formats to lowercase."""
        if isinstance(v, str):
            return v.lower()
        elif isinstance(v, list):
            return [fmt.lower() for fmt in v]
        return v


class CreateJobResponse(BaseModel):
    """Response after creating a job."""

    job_id: str = Field(..., description="Unique job identifier")
    file_id: str = Field(..., description="Unique file identifier for uploads")
    status: str = Field(..., description="Current job status")
    message: str = Field(..., description="Success message")


class UploadChunkRequest(BaseModel):
    """Request to upload a file chunk."""

    chunk_index: int = Field(
        ...,
        description="Chunk index (0-based)",
        ge=0,
    )


class UploadChunkResponse(BaseModel):
    """Response after uploading a chunk."""

    job_id: str = Field(..., description="Job identifier")
    chunk_index: int = Field(..., description="Uploaded chunk index")
    chunks_uploaded: int = Field(..., description="Total chunks uploaded so far")
    total_chunks: int = Field(..., description="Total expected chunks")
    is_complete: bool = Field(..., description="Whether all chunks are uploaded")
    message: str = Field(..., description="Status message")


class MergeChunksResponse(BaseModel):
    """Response after merging chunks."""

    job_id: str = Field(..., description="Job identifier")
    file_id: str = Field(..., description="File identifier")
    merged: bool = Field(..., description="Whether chunks were merged")
    total_chunks: int | None = Field(None, description="Number of chunks merged")
    file_size: int = Field(..., description="Final file size in bytes")
    reason: str | None = Field(None, description="Reason if not merged")
    message: str = Field(..., description="Status message")


class StartConversionRequest(BaseModel):
    """Request to start conversion process."""

    pass  # No additional fields needed, job_id comes from path


class StartConversionResponse(BaseModel):
    """Response after starting conversion."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Status message")


class JobStatusResponse(BaseModel):
    """Job status information."""

    job_id: str = Field(..., description="Job identifier")
    file_id: str | None = Field(None, description="File identifier")
    status: str = Field(..., description="Current job status")
    input_format: str | None = Field(None, description="Input format")
    output_format: str | None = Field(None, description="Output format")
    file_size_bytes: int = Field(0, description="File size in bytes")
    output_size_bytes: int = Field(0, description="Output file size in bytes")
    chunks_uploaded: int = Field(0, description="Chunks uploaded")
    total_chunks: int = Field(0, description="Total chunks")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    processing_time_seconds: float = Field(
        0.0, description="Processing time in seconds"
    )
    error_message: str | None = Field(None, description="Error message if failed")
    worker_id: str | None = Field(None, description="Worker ID if processing")
    output_file_path: str | None = Field(
        None, description="Output file path if completed"
    )
    version: int = Field(0, description="Event version")


class CancelJobRequest(BaseModel):
    """Request to cancel a job."""

    reason: str | None = Field(None, description="Optional cancellation reason")


class CancelJobResponse(BaseModel):
    """Response after cancelling a job."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: dict | None = Field(None, description="Additional error details")
