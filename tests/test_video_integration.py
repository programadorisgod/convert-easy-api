"""Integration tests for VideoConverter with real FFmpeg.

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
async def sample_video(tmp_path: Path) -> Path:
    """Generate a small synthetic video using FFmpeg.

    Creates a 1-second test video with color bars for testing.
    """
    output = tmp_path / "test_src.mp4"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        str(output),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()

    if not output.exists():
        pytest.fail("Failed to generate sample video")
    return output


class TestVideoConverterReal:
    """Integration tests with real FFmpeg subprocess."""

    @pytest.mark.integration
    async def test_convert_mp4_to_mkv(self, ffmpeg_available, sample_video, tmp_path):
        """Convert MP4 to MKV to verify basic conversion works."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "converted"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mkv",
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_mp4_to_mp4_default(self, ffmpeg_available, sample_video, tmp_path):
        """Convert MP4 to MP4 without extra parameters (standard re-encoding/web optimization)."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "mp4_to_mp4"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp4",
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_with_crf(self, ffmpeg_available, sample_video, tmp_path):
        """Converting with CRF override produces valid output."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "crf_test"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp4",
            crf=28,
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_with_resolution(self, ffmpeg_available, sample_video, tmp_path):
        """Converting with resolution scaling produces valid output."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "res_test"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp4",
            resolution="160:120",
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_convert_with_fps(self, ffmpeg_available, sample_video, tmp_path):
        """Converting with FPS change produces valid output."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "fps_test"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp4",
            fps=5,
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_extract_audio(self, ffmpeg_available, sample_video, tmp_path):
        """Extract audio from video produces valid audio file."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "audio_out"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp3",
            extract_audio=True,
            audio_output_format="mp3",
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_remove_audio(self, ffmpeg_available, sample_video, tmp_path):
        """Remove audio track from video produces valid output."""
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "no_audio"
        result = await converter.convert(
            input_path=sample_video,
            output_path=output,
            output_format="mp4",
            remove_audio=True,
        )
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.integration
    async def test_unsupported_output_raises_error(
        self, ffmpeg_available, sample_video, tmp_path
    ):
        """Converting to unsupported format raises UnsupportedFormatError."""
        from shared.exceptions import UnsupportedFormatError
        from src.infrastructure.converters.video_converter import get_video_converter

        converter = get_video_converter()
        output = tmp_path / "invalid"

        with pytest.raises(UnsupportedFormatError):
            await converter.convert(
                input_path=sample_video,
                output_path=output,
                output_format="wmv",  # Not in OUTPUT_FORMATS
            )
