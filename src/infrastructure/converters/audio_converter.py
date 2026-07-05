"""Audio conversion utility using FFmpeg.

Converts between audio formats and applies optional processing:
bitrate, sample rate, channels, trimming, volume normalization.

Follows the same subprocess pattern as DocumentConverter.
"""

import asyncio
import logging
import shutil
from pathlib import Path

from shared.config import get_settings
from shared.exceptions import ProcessingError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class AudioConverter:
    """Converts audio files using FFmpeg subprocess.

    Supports format conversion between common audio formats plus optional
    processing parameters like bitrate, sample rate, channels, trimming,
    and volume normalization.
    """

    # All supported input formats. FFmpeg can handle many more, but these
    # are the ones we explicitly allow through our API.
    INPUT_FORMATS = frozenset({
        "mp3", "wav", "aac", "m4a", "flac",
        "ogg", "opus", "wma", "aiff", "amr",
    })

    # Supported output formats. WMA/AIFF/AMR omitted — proprietary or niche.
    OUTPUT_FORMATS = frozenset({
        "mp3", "wav", "aac", "m4a", "flac", "ogg", "opus",
    })

    # Map output format to FFmpeg audio encoder.
    # ponytail: using native aac encoder (libfdk_aac has license issues)
    AUDIO_ENCODERS: dict[str, str] = {
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
        bitrate: str | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
        trim_start: str | None = None,
        trim_duration: int | None = None,
        normalize_volume: bool = False,
    ) -> Path:
        """Convert audio file using FFmpeg.

        Args:
            input_path: Path to input audio file.
            output_path: Path for the converted output (extensionless storage path).
            output_format: Target format (mp3, wav, flac, ogg, opus, aac, m4a).
            bitrate: Audio bitrate (e.g. '128k', '192k', '256k', '320k').
            sample_rate: Sample rate in Hz (e.g. 22050, 44100, 48000).
            channels: Channel count (1=mono, 2=stereo).
            trim_start: Start timestamp for trimming (HH:MM:SS).
            trim_duration: Duration in seconds for trimming.
            normalize_volume: Enable dynaudnorm volume normalization.

        Returns:
            Path to the converted output file.

        Raises:
            UnsupportedFormatError: If format is not supported.
            ProcessingError: If conversion fails or FFmpeg is not available.
        """
        out_fmt = output_format.lower().lstrip(".")

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
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
            trim_start=trim_start,
            trim_duration=trim_duration,
            normalize_volume=normalize_volume,
        )

        await self._run_command(cmd)

        # Normalize to storage canonical path (extensionless).
        desired = output_path.with_suffix(f".{out_fmt}")
        if desired.exists() and desired != output_path:
            if output_path.exists():
                output_path.unlink()
            desired.replace(output_path)

        if not output_path.exists():
            raise ProcessingError("Audio conversion did not produce an output file")

        return output_path

    def _build_ffmpeg_command(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
        bitrate: str | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
        trim_start: str | None = None,
        trim_duration: int | None = None,
        normalize_volume: bool = False,
    ) -> list[str]:
        """Build the FFmpeg command argument list.

        Args:
            Same as convert().

        Returns:
            List of command arguments for create_subprocess_exec.
        """
        # Guarded by convert() check, but mypy can't track cross-method narrowing.
        assert self._ffmpeg_path is not None
        cmd: list[str] = [
            self._ffmpeg_path,
            "-y",  # Overwrite output without asking
            "-i",
            str(input_path),
        ]

        # Seek after input for accurate trimming (decodes from seek point).
        if trim_start:
            cmd.extend(["-ss", trim_start])

        if trim_duration:
            cmd.extend(["-t", str(trim_duration)])

        # Audio codec mapping.
        encoder = self.AUDIO_ENCODERS.get(output_format)
        if encoder:
            cmd.extend(["-c:a", encoder])

        if bitrate:
            cmd.extend(["-b:a", bitrate])

        if sample_rate:
            cmd.extend(["-ar", str(sample_rate)])

        if channels:
            cmd.extend(["-ac", str(channels)])

        # ponytail: dynaudnorm over loudnorm — single-pass, no 2-pass needed
        if normalize_volume:
            cmd.extend(["-af", "dynaudnorm"])

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
                timeout=self.settings.max_audio_conversion_time_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ProcessingError("Audio conversion timed out")

        if process.returncode != 0:
            stderr_text = stderr.decode().strip() if stderr else ""
            stdout_text = stdout.decode().strip() if stdout else ""
            details = stderr_text or stdout_text or "unknown error"
            raise ProcessingError(f"Audio conversion failed: {details}")

        return (
            stdout.decode().strip() if stdout else "",
            stderr.decode().strip() if stderr else "",
        )


_audio_converter: AudioConverter | None = None


def get_audio_converter() -> AudioConverter:
    """Get singleton audio converter instance."""
    global _audio_converter
    if _audio_converter is None:
        _audio_converter = AudioConverter()
    return _audio_converter
