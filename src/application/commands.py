"""Application commands (DTOs for use cases).

Commands represent the intent to perform an action. They are immutable
data structures that flow from the presentation layer to handlers.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CreateJobCommand:
    """Command to create a new conversion job.

    Attributes:
        input_format: Input file format (e.g., 'png')
        output_formats: List of desired output formats
        original_size: Size of original file in bytes
        total_chunks: Number of chunks for upload (1 for non-chunked)
        metadata: Optional metadata dict
    """

    input_format: str
    output_formats: list[str]
    original_size: int
    total_chunks: int = 1
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class UploadChunkCommand:
    """Command to upload a file chunk.

    Attributes:
        job_id: Job identifier
        chunk_index: Chunk index (0-based)
        chunk_data: Raw chunk bytes
    """

    job_id: str
    chunk_index: int
    chunk_data: bytes


@dataclass(frozen=True)
class UploadCompleteFileCommand:
    """Command to upload a complete file (no chunking).

    Attributes:
        job_id: Job identifier
        file_data: Complete file bytes
    """

    job_id: str
    file_data: bytes


@dataclass(frozen=True)
class MergeChunksCommand:
    """Command to merge uploaded chunks into single file.

    Attributes:
        job_id: Job identifier
    """

    job_id: str


@dataclass(frozen=True)
class StartConversionCommand:
    """Command to start the conversion process.

    Attributes:
        job_id: Job identifier
    """

    job_id: str


@dataclass(frozen=True)
class CancelJobCommand:
    """Command to cancel a job.

    Attributes:
        job_id: Job identifier
        reason: Optional cancellation reason
    """

    job_id: str
    reason: str | None = None


@dataclass(frozen=True)
class GetJobStatusCommand:
    """Command to retrieve job status.

    Attributes:
        job_id: Job identifier
    """

    job_id: str


@dataclass(frozen=True)
class DownloadResultCommand:
    """Command to download conversion result.

    Attributes:
        job_id: Job identifier
        output_format: Desired output format
    """

    job_id: str
    output_format: str
