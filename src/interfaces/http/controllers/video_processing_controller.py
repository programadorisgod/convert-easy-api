"""Video processing controller for FFmpeg-based conversion."""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from shared.exceptions import JobNotFoundError, ValidationError
from src.application.commands import ProcessVideoCommand
from src.application.handlers import ProcessVideoHandler
from src.infrastructure.persistence import JobRepository
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_queue, get_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Video Processing"])


class ProcessVideoRequest(BaseModel):
    """Request to convert uploaded video file."""

    job_id: str = Field(..., description="Job identifier from upload workflow")
    output_format: str = Field(
        ...,
        description="Target format (mp4, mkv, mov, avi, webm, flv, mpeg, m4v)",
    )
    crf: int | None = Field(
        None,
        ge=0,
        le=51,
        description="CRF value for quality (0-51, lower=better, default 23 for libx264)",
    )
    resolution: str | None = Field(
        None,
        description="Target resolution as WIDTH:HEIGHT (e.g. '1920:1080' or '-1:480')",
    )
    fps: int | None = Field(
        None, ge=1, description="Target FPS (e.g. 24, 30, 60)"
    )
    trim_start: str | None = Field(
        None, description="Trim start timestamp (HH:MM:SS)"
    )
    trim_duration: int | None = Field(
        None, ge=1, description="Trim duration in seconds"
    )
    extract_audio: bool = Field(
        False, description="Extract audio track instead of converting video"
    )
    audio_output_format: str | None = Field(
        None, description="Audio format for extraction (mp3, wav, aac, flac, ogg, opus, m4a)"
    )
    audio_bitrate: str | None = Field(
        None, description="Audio bitrate for extraction (e.g. '192k')"
    )
    remove_audio: bool = Field(
        False, description="Remove audio track from video"
    )


class ProcessVideoResponse(BaseModel):
    """Response for video processing operation."""

    job_id: str
    status: str
    message: str
    video_config: dict


@router.post(
    "/video",
    response_model=ProcessVideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process video conversion",
    description="Queue a video conversion job using FFmpeg with optional parameters.",
)
async def process_video(
    request: ProcessVideoRequest,
    repository: JobRepository = Depends(get_repository),
    queue: BullMQAdapter = Depends(get_queue),
    storage: FileStorage = Depends(get_storage),
) -> ProcessVideoResponse:
    """Queue video conversion for an uploaded file using FFmpeg."""
    try:
        command = ProcessVideoCommand(
            job_id=request.job_id,
            output_format=request.output_format.lower(),
            crf=request.crf,
            resolution=request.resolution,
            fps=request.fps,
            trim_start=request.trim_start,
            trim_duration=request.trim_duration,
            extract_audio=request.extract_audio,
            audio_output_format=request.audio_output_format.lower() if request.audio_output_format else None,
            audio_bitrate=request.audio_bitrate,
            remove_audio=request.remove_audio,
        )

        handler = ProcessVideoHandler(repository, queue, storage)
        result = await handler.handle(command)

        return ProcessVideoResponse(
            job_id=result["job_id"],
            status=result["status"],
            message="Video conversion queued successfully.",
            video_config=result["video_config"],
        )

    except (JobNotFoundError, ValidationError) as e:
        logger.warning(f"Video processing failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing video: {e}", exc_info=True)
        raise
