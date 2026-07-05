"""Video conversion utility using FFmpeg.

Converts between video formats and applies optional processing:
CRF compression, resolution scaling, FPS adjustment, trimming,
audio extraction, and audio removal.

Follows the same subprocess pattern as AudioConverter.
"""

import asyncio
import logging
import shutil
from pathlib import Path

from shared.config import get_settings
from shared.exceptions import ProcessingError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class VideoConverter:
    """Converts video files using FFmpeg subprocess.

    Supports format conversion between common video formats plus optional
    processing parameters like CRF, resolution, FPS, trimming, audio
    extraction, and audio removal.
    """

    # All supported input formats.
    INPUT_FORMATS = frozenset({
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "wmv", "mpeg", "3gp", "m4v",
    })

    # Supported output formats. WMV/3GP excluded (proprietary/legacy).
    OUTPUT_FORMATS = frozenset({
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "mpeg", "m4v",
    })

    # Map output format to FFmpeg video encoder.
    VIDEO_ENCODERS: dict[str, str] = {
        "mp4": "libx264",
        "mkv": "libx264",
        "mov": "libx264",
        "avi": "mpeg4",
        "webm": "libvpx-vp9",
        "flv": "flv",
        "mpeg": "mpeg2video",
        "m4v": "libx264",
    }

    # Audio encoders used when extract_audio=True.
    PREFERRED_AUDIO_ENCODERS: dict[str, str] = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "aac": "aac",
        "m4a": "aac",
        "flac": "flac",
        "ogg": "libvorbis",
        "opus": "libopus",
    }

    def __init__(self) -> None:
        """Initialize converter and check FFmpeg availability."""
        self.settings = get_settings()
        self._ffmpeg_path = shutil.which("ffmpeg")

    async def convert(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
        crf: int | None = None,
        resolution: str | None = None,
        fps: int | None = None,
        trim_start: str | None = None,
        trim_duration: int | None = None,
        extract_audio: bool = False,
        audio_output_format: str | None = None,
        audio_bitrate: str | None = None,
        remove_audio: bool = False,
    ) -> Path:
        """Convert video file using FFmpeg.

        Args:
            input_path: Path to input video file.
            output_path: Path for the converted output (extensionless storage path).
            output_format: Target format (mp4, mkv, mov, avi, webm, flv, mpeg, m4v).
            crf: CRF value (0-51, lower=better quality, default 23 for libx264).
            resolution: Resolution string (e.g. '1920:1080' or '-1:480').
            fps: Target FPS (e.g. 24, 30, 60).
            trim_start: Start timestamp (HH:MM:SS).
            trim_duration: Duration in seconds.
            extract_audio: Extract audio track instead of converting video.
            audio_output_format: Audio format for extraction.
            audio_bitrate: Bitrate for extracted audio (e.g. '192k').
            remove_audio: Remove audio track from video.

        Returns:
            Path to the converted output file.

        Raises:
            UnsupportedFormatError: If format is not supported.
            ProcessingError: If conversion fails or FFmpeg is not available.
        """
        out_fmt = output_format.lower().lstrip(".")

        if extract_audio:
            if not audio_output_format:
                raise ProcessingError(
                    "audio_output_format is required when extract_audio=True"
                )
            audio_fmt = audio_output_format.lower().lstrip(".")
            if audio_fmt not in self.PREFERRED_AUDIO_ENCODERS:
                raise UnsupportedFormatError(
                    audio_fmt,
                    supported_formats=sorted(self.PREFERRED_AUDIO_ENCODERS),
                )
        else:
            if out_fmt not in self.OUTPUT_FORMATS:
                raise UnsupportedFormatError(
                    out_fmt,
                    supported_formats=sorted(self.OUTPUT_FORMATS),
                )

        if not self._ffmpeg_path:
            raise ProcessingError(
                "FFmpeg is not installed in the runtime image. "
                "Install it with: apt-get install ffmpeg"
            )

        cmd = self._build_ffmpeg_command(
            input_path=input_path,
            output_path=output_path,
            output_format=out_fmt,
            crf=crf,
            resolution=resolution,
            fps=fps,
            trim_start=trim_start,
            trim_duration=trim_duration,
            extract_audio=extract_audio,
            audio_output_format=audio_output_format,
            audio_bitrate=audio_bitrate,
            remove_audio=remove_audio,
        )

        await self._run_command(cmd)

        # Normalize to storage canonical path (extensionless).
        desired = output_path.with_suffix(f".{out_fmt}")
        if desired.exists() and desired != output_path:
            if output_path.exists():
                output_path.unlink()
            desired.replace(output_path)

        if not output_path.exists():
            raise ProcessingError("Video conversion did not produce an output file")

        return output_path

    def _build_ffmpeg_command(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
        crf: int | None = None,
        resolution: str | None = None,
        fps: int | None = None,
        trim_start: str | None = None,
        trim_duration: int | None = None,
        extract_audio: bool = False,
        audio_output_format: str | None = None,
        audio_bitrate: str | None = None,
        remove_audio: bool = False,
    ) -> list[str]:
        """Build the FFmpeg command argument list.

        Three branching paths:
        1. extract_audio=True: -vn -c:a {audio_enc} [audio_bitrate]
        2. remove_audio=True: -c:v {video_enc} params + -an
        3. Normal: -c:v {video_enc} params

        Args:
            Same as convert().

        Returns:
            List of command arguments for create_subprocess_exec.
        """
        assert self._ffmpeg_path is not None
        cmd: list[str] = [
            self._ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
        ]

        # Seek after input for accurate trimming.
        if trim_start:
            cmd.extend(["-ss", trim_start])
        if trim_duration:
            cmd.extend(["-t", str(trim_duration)])

        if extract_audio:
            # Extract audio only — no video stream.
            cmd.extend(["-vn"])
            audio_fmt = audio_output_format.lower().lstrip(".") if audio_output_format else ""
            encoder = self.PREFERRED_AUDIO_ENCODERS.get(audio_fmt)
            if encoder:
                cmd.extend(["-c:a", encoder])
            if audio_bitrate:
                cmd.extend(["-b:a", audio_bitrate])
        elif remove_audio:
            # Remove audio track, keep video.
            video_enc = self.VIDEO_ENCODERS.get(output_format)
            if video_enc:
                cmd.extend(["-c:v", video_enc])
            if crf is not None:
                cmd.extend(["-crf", str(crf)])
            if resolution:
                cmd.extend(["-vf", f"scale={resolution}"])
            if fps:
                cmd.extend(["-r", str(fps)])
            cmd.extend(["-an"])
        else:
            # Normal video conversion.
            video_enc = self.VIDEO_ENCODERS.get(output_format)
            if video_enc:
                cmd.extend(["-c:v", video_enc])
            if crf is not None:
                cmd.extend(["-crf", str(crf)])
            if resolution:
                cmd.extend(["-vf", f"scale={resolution}"])
            if fps:
                cmd.extend(["-r", str(fps)])

        cmd.append(str(output_path.with_suffix(f".{output_format}")))
        return cmd

    async def _run_command(self, cmd: list[str]) -> tuple[str, str]:
        """Execute FFmpeg subprocess with timeout.

        Args:
            cmd: Command list for create_subprocess_exec.

        Returns:
            Tuple of (stdout_text, stderr_text).

        Raises:
            ProcessingError: If command times out or returns non-zero.
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.max_video_conversion_time_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ProcessingError("Video conversion timed out")

        if process.returncode != 0:
            stderr_text = stderr.decode().strip() if stderr else ""
            stdout_text = stdout.decode().strip() if stdout else ""
            details = stderr_text or stdout_text or "unknown error"
            raise ProcessingError(f"Video conversion failed: {details}")

        return (
            stdout.decode().strip() if stdout else "",
            stderr.decode().strip() if stderr else "",
        )


_video_converter: VideoConverter | None = None


def get_video_converter() -> VideoConverter:
    """Get singleton video converter instance."""
    global _video_converter
    if _video_converter is None:
        _video_converter = VideoConverter()
    return _video_converter
