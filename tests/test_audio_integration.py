"""Integration tests for AudioConverter with real FFmpeg.

These tests require FFmpeg to be installed on the system.
Marked with @pytest.mark.integration to allow skipping in CI.
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from shared.exceptions import ProcessingError


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ffmpeg_available():
    """Skip if FFmpeg is not installed."""
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg not installed on this system")
    return True


@pytest.fixture
async def sample_audio(tmp_path: Path) -> Path:
    """Generate a small synthetic audio file using FFmpeg.

    Creates a 1-second sine wave WAV file for testing.
    This is fast (~0.1s) and avoids test data dependencies.
    """
    output = tmp_path / "sine.wav"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1",
        str(output),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()

    if not output.exists():
        pytest.fail("Failed to generate sample audio")
    return output


class TestAudioConverterReal:
    """Integration tests with real FFmpeg subprocess."""

    @pytest.mark.integration
    async def test_convert_mp3_to_wav(self, ffmpeg_available, sample_audio, tmp_path):
        """Convert synthetic WAV to MP3 and back to verify pipeline works."""
        from src.infrastructure.converters.audio_converter import get_audio_converter

        converter = get_audio_converter()

        # Step 1: WAV → MP3
        mp3_output = tmp_path / "step1"
        result = await converter.convert(
            input_path=sample_audio,
            output_path=mp3_output,
            output_format="mp3",
        )
        assert result.exists()
        assert result.stat().st_size > 0

        # Step 2: MP3 → WAV (verify round-trip)
        wav_output = tmp_path / "step2"
        result2 = await converter.convert(
            input_path=result,
            output_path=wav_output,
            output_format="wav",
        )
        assert result2.exists()
        assert result2.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_with_bitrate(self, ffmpeg_available, sample_audio, tmp_path):
        """Converting with bitrate override produces valid output."""
        from src.infrastructure.converters.audio_converter import get_audio_converter

        converter = get_audio_converter()
        output = tmp_path / "bitrate_test"
        result = await converter.convert(
            input_path=sample_audio,
            output_path=output,
            output_format="mp3",
            bitrate="128k",
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_to_mono(self, ffmpeg_available, sample_audio, tmp_path):
        """Converting stereo to mono produces valid output."""
        from src.infrastructure.converters.audio_converter import get_audio_converter

        converter = get_audio_converter()
        output = tmp_path / "mono_test"
        result = await converter.convert(
            input_path=sample_audio,
            output_path=output,
            output_format="mp3",
            channels=1,
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_flac_to_ogg(self, ffmpeg_available, sample_audio, tmp_path):
        """Convert from WAV to FLAC to OGG format chain."""
        from src.infrastructure.converters.audio_converter import get_audio_converter

        converter = get_audio_converter()

        flac_out = tmp_path / "flac_step"
        result = await converter.convert(
            input_path=sample_audio,
            output_path=flac_out,
            output_format="flac",
        )
        assert result.exists()

        ogg_out = tmp_path / "ogg_step"
        result2 = await converter.convert(
            input_path=result,
            output_path=ogg_out,
            output_format="ogg",
        )
        assert result2.exists()
        assert result2.stat().st_size > 0

    @pytest.mark.integration
    async def test_unsupported_output_raises_error(
        self, ffmpeg_available, sample_audio, tmp_path
    ):
        """Converting to unsupported format raises UnsupportedFormatError."""
        from shared.exceptions import UnsupportedFormatError
        from src.infrastructure.converters.audio_converter import get_audio_converter

        converter = get_audio_converter()
        output = tmp_path / "invalid"

        with pytest.raises(UnsupportedFormatError):
            await converter.convert(
                input_path=sample_audio,
                output_path=output,
                output_format="wma",  # Not in OUTPUT_FORMATS
            )
