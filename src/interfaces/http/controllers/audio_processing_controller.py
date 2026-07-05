"""Audio processing controller for FFmpeg-based conversion."""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import ProcessAudioCommand
from src.application.handlers import ProcessAudioHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Audio Processing"])


class ProcessAudioRequest(BaseModel):
    """Request to convert uploaded audio file."""

    job_id: str = Field(..., description="Job identifier from upload workflow")
    output_format: str = Field(
        ..., description="Target format (mp3, wav, flac, ogg, opus, aac, m4a)"
    )
    bitrate: str | None = Field(
        None, description="Audio bitrate: 128k, 192k, 256k, 320k"
    )
    sample_rate: int | None = Field(
        None, description="Sample rate in Hz: 22050, 44100, 48000"
    )
    channels: int | None = Field(
        None, description="Channel count: 1 (mono) or 2 (stereo)"
    )
    trim_start: str | None = Field(
        None, description="Trim start timestamp (HH:MM:SS)"
    )
    trim_duration: int | None = Field(
        None, description="Trim duration in seconds"
    )
    normalize_volume: bool = Field(
        False, description="Enable dynamic volume normalization"
    )


class ProcessAudioResponse(BaseModel):
    """Response for audio processing operation."""

    job_id: str
    status: str
    message: str
    audio_config: dict


@router.post(
    "/audio",
    response_model=ProcessAudioResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process audio conversion",
    description="Queue an audio conversion job using FFmpeg with optional parameters.",
)
async def process_audio(
    request: ProcessAudioRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessAudioResponse:
    """Queue audio conversion for an uploaded file using FFmpeg."""
    try:
        command = ProcessAudioCommand(
            job_id=request.job_id,
            output_format=request.output_format.lower(),
            bitrate=request.bitrate,
            sample_rate=request.sample_rate,
            channels=request.channels,
            trim_start=request.trim_start,
            trim_duration=request.trim_duration,
            normalize_volume=request.normalize_volume,
        )

        handler = ProcessAudioHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessAudioResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Audio conversion queued successfully.",
            audio_config=result["audio_config"],
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Audio processing failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing audio: {e}", exc_info=True)
        raise
