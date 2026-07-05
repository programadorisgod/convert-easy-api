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


# Image processing commands (Fase 1)


@dataclass(frozen=True)
class ProcessImageCommand:
    """Command to process image with advanced operations.

    This command configures the image processing pipeline including:
    - Background removal (optional)
    - Compression (optional)
    - Watermarking (optional)
    - Format conversion (always)

    Attributes:
        job_id: Job identifier
        output_format: Target image format
        remove_background: Enable background removal
        background_model: Model for background removal (u2net, etc.)
        alpha_matting: Enable alpha matting for better edges
        compress_enabled: Enable compression
        compression_level: Compression level (low, balanced, strong)
        compression_quality: Optional quality override (0-100)
        watermark_enabled: Enable watermark
        watermark_type: Watermark type (text, logo)
        watermark_params: Watermark parameters dict
        output_quality: Optional output quality (0-100)
        strip_metadata: Strip EXIF metadata for privacy
    """

    job_id: str
    output_format: str

    # Background removal
    remove_background: bool = False
    background_model: str = "u2net"
    alpha_matting: bool = False

    # Compression
    compress_enabled: bool = False
    compression_level: str = "balanced"  # low, balanced, strong
    compression_quality: int | None = None

    # Watermark
    watermark_enabled: bool = False
    watermark_type: str | None = None  # text, logo
    watermark_params: dict[str, Any] | None = None

    # Output
    output_quality: int | None = None
    strip_metadata: bool = True


@dataclass(frozen=True)
class ProcessDocumentCommand:
    """Command to process document conversion (Phase 2).

    Attributes:
        job_id: Job identifier
        output_format: Target document format
        preferred_engine: Optional engine override (auto, pandoc, libreoffice)
    """

    job_id: str
    output_format: str
    preferred_engine: str = "auto"


@dataclass(frozen=True)
class ProcessAudioCommand:
    """Command to process audio conversion using FFmpeg.

    Attributes:
        job_id: Job identifier
        output_format: Target audio format (mp3, wav, flac, ogg, opus, aac, m4a)
        bitrate: Optional audio bitrate (e.g., '128k', '192k', '256k', '320k')
        sample_rate: Optional sample rate in Hz (e.g., 22050, 44100, 48000)
        channels: Optional channel count (1 for mono, 2 for stereo)
        trim_start: Optional start timestamp for trimming (HH:MM:SS)
        trim_duration: Optional duration in seconds for trimming
        normalize_volume: Enable dynamic volume normalization
    """

    job_id: str
    output_format: str
    bitrate: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    trim_start: str | None = None
    trim_duration: int | None = None
    normalize_volume: bool = False


@dataclass(frozen=True)
class ProcessVideoCommand:
    """Command to process video conversion using FFmpeg.

    Attributes:
        job_id: Job identifier
        output_format: Target video format (mp4, mkv, mov, avi, webm, flv, mpeg, m4v)
        crf: Optional CRF value (0-51, lower=better quality, default 23 for libx264)
        resolution: Optional resolution (e.g., '1920:1080' or '-1:480 for aspect-safe)
        fps: Optional FPS value (e.g., 24, 30, 60)
        trim_start: Optional start timestamp (HH:MM:SS)
        trim_duration: Optional duration in seconds
        extract_audio: Extract audio track instead of converting video
        audio_output_format: Audio format for extraction (mp3, wav, aac, flac, ogg, opus, m4a)
        remove_audio: Remove audio track from video
    """

    job_id: str
    output_format: str
    crf: int | None = None
    resolution: str | None = None
    fps: int | None = None
    trim_start: str | None = None
    trim_duration: int | None = None
    extract_audio: bool = False
    audio_output_format: str | None = None
    audio_bitrate: str | None = None
    remove_audio: bool = False


@dataclass(frozen=True)
class ProcessPdfCommand:
    """Command to process PDF operations.

    Attributes:
        job_id: Primary PDF job identifier
        operation: PDF operation name
        operation_params: Operation-specific payload
        source_job_ids: Additional PDF job IDs for merge-like operations
    """

    job_id: str
    operation: str
    operation_params: dict[str, Any] | None = None
    source_job_ids: list[str] | None = None
