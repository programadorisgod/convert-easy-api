"""Unit tests for VideoConverter.

Tests command construction, codec mapping, handler validation,
and error handling without calling FFmpeg (unit scope).
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.config import get_settings
from shared.exceptions import UnsupportedFormatError, ValidationError


class TestVideoConverterCodecMapping:
    """Verify codec mapping for each output format."""

    EXPECTED_VIDEO_ENCODERS = {
        "mp4": "libx264",
        "mkv": "libx264",
        "mov": "libx264",
        "avi": "mpeg4",
        "webm": "libvpx-vp9",
        "flv": "flv",
        "mpeg": "mpeg2video",
        "m4v": "libx264",
    }

    EXPECTED_AUDIO_ENCODERS = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "aac": "aac",
        "m4a": "aac",
        "flac": "flac",
        "ogg": "libvorbis",
        "opus": "libopus",
    }

    def test_all_output_formats_have_video_encoders(self):
        """Every supported output format must have a video codec mapping."""
        from src.infrastructure.converters.video_converter import VideoConverter

        assert VideoConverter.OUTPUT_FORMATS == set(self.EXPECTED_VIDEO_ENCODERS.keys())

    def test_video_encoder_mapping_matches(self):
        """Each video format maps to the expected FFmpeg encoder."""
        from src.infrastructure.converters.video_converter import VideoConverter

        for fmt, expected_encoder in self.EXPECTED_VIDEO_ENCODERS.items():
            assert VideoConverter.VIDEO_ENCODERS[fmt] == expected_encoder

    def test_audio_encoder_mapping_matches(self):
        """Each audio extraction format maps to the expected encoder."""
        from src.infrastructure.converters.video_converter import VideoConverter

        for fmt, expected_encoder in self.EXPECTED_AUDIO_ENCODERS.items():
            assert VideoConverter.PREFERRED_AUDIO_ENCODERS[fmt] == expected_encoder


class TestVideoConverterInputFormats:
    """Verify input format list."""

    EXPECTED_INPUTS = {
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "wmv", "mpeg", "3gp", "m4v",
    }

    def test_input_formats_match_settings(self):
        """VideoConverter input formats should match settings list."""
        from src.infrastructure.converters.video_converter import VideoConverter

        settings = get_settings()
        assert VideoConverter.INPUT_FORMATS == set(settings.supported_video_input_formats)

    def test_input_formats_contain_all_expected(self):
        from src.infrastructure.converters.video_converter import VideoConverter

        assert VideoConverter.INPUT_FORMATS == self.EXPECTED_INPUTS


class TestVideoConverterOutputFormats:
    """Verify output format list."""

    EXPECTED_OUTPUTS = {
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "mpeg", "m4v",
    }

    def test_output_formats_match_settings(self):
        """VideoConverter output formats should match settings list."""
        from src.infrastructure.converters.video_converter import VideoConverter

        settings = get_settings()
        assert VideoConverter.OUTPUT_FORMATS == set(settings.supported_video_output_formats)

    def test_output_formats_contain_all_expected(self):
        from src.infrastructure.converters.video_converter import VideoConverter

        assert VideoConverter.OUTPUT_FORMATS == self.EXPECTED_OUTPUTS


class TestVideoConverterCommandBuilding:
    """Test FFmpeg command construction via _build_ffmpeg_command.

    These tests instantiate VideoConverter but only test the
    command-building logic — no subprocess is executed.
    """

    @pytest.fixture
    def converter(self):
        """Fixture that patches ffmpeg path to avoid 'not installed' errors."""
        from src.infrastructure.converters.video_converter import VideoConverter

        c = VideoConverter()
        c._ffmpeg_path = "/usr/bin/ffmpeg"
        return c

    def test_basic_conversion_command(self, converter):
        """Simple mp4→mkv should include input, output, and video encoder."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/test.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mkv",
        )
        assert "/usr/bin/ffmpeg" in cmd
        assert "-y" in cmd
        assert "-i" in cmd
        input_idx = cmd.index("-i")
        assert cmd[input_idx + 1] == "/tmp/test.mp4"
        assert cmd[-1] == "/tmp/out.mkv"
        assert "-c:v" in cmd
        cv_idx = cmd.index("-c:v")
        assert cmd[cv_idx + 1] == "libx264"

    def test_crf_option(self, converter):
        """CRF option adds -crf with value."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            crf=23,
        )
        assert "-crf" in cmd
        crf_idx = cmd.index("-crf")
        assert cmd[crf_idx + 1] == "23"

    def test_resolution_option(self, converter):
        """Resolution adds -vf scale=WIDTH:HEIGHT."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            resolution="1920:1080",
        )
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        assert cmd[vf_idx + 1] == "scale=1920:1080"

    def test_fps_option(self, converter):
        """FPS option adds -r with value."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            fps=30,
        )
        assert "-r" in cmd
        r_idx = cmd.index("-r")
        assert cmd[r_idx + 1] == "30"

    def test_trim_start_and_duration(self, converter):
        """Trim options add -ss and -t after input."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            trim_start="00:01:00",
            trim_duration=30,
        )
        assert "-ss" in cmd
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "00:01:00"
        assert "-t" in cmd
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "30"

    def test_extract_audio(self, converter):
        """Extract audio uses -map 0:a:0 and audio encoder, no video encoder."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            extract_audio=True,
            audio_output_format="mp3",
        )
        assert "-map" in cmd
        map_idx = cmd.index("-map")
        assert cmd[map_idx + 1] == "0:a:0"
        assert "-c:v" not in cmd
        assert "-c:a" in cmd
        ca_idx = cmd.index("-c:a")
        assert cmd[ca_idx + 1] == "libmp3lame"
        assert cmd[-1] == "/tmp/out.mp3"

    def test_extract_audio_with_bitrate(self, converter):
        """Extract audio with bitrate adds -b:a."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            extract_audio=True,
            audio_output_format="mp3",
            audio_bitrate="192k",
        )
        assert "-map" in cmd and cmd[cmd.index("-map") + 1] == "0:a:0"
        assert "-b:a" in cmd
        ba_idx = cmd.index("-b:a")
        assert cmd[ba_idx + 1] == "192k"

    def test_remove_audio(self, converter):
        """Remove audio adds -an, keeps video encoder."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            remove_audio=True,
        )
        assert "-an" in cmd
        assert "-c:v" in cmd
        cv_idx = cmd.index("-c:v")
        assert cmd[cv_idx + 1] == "libx264"
        assert "-c:a" not in cmd

    def test_remove_audio_with_crf_resolution_fps(self, converter):
        """Remove audio with CRF, resolution, FPS — all params present."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mp4",
            crf=28,
            resolution="1280:720",
            fps=24,
            remove_audio=True,
        )
        assert "-crf" in cmd and cmd[cmd.index("-crf") + 1] == "28"
        assert "-vf" in cmd and cmd[cmd.index("-vf") + 1] == "scale=1280:720"
        assert "-r" in cmd and cmd[cmd.index("-r") + 1] == "24"
        assert "-an" in cmd

    def test_all_options_together(self, converter):
        """All normal conversion options combined produce a valid command."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out"),
            output_format="mkv",
            crf=23,
            resolution="1920:1080",
            fps=30,
            trim_start="00:01:00",
            trim_duration=60,
        )
        assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
        assert "-crf" in cmd and cmd[cmd.index("-crf") + 1] == "23"
        assert "-vf" in cmd and cmd[cmd.index("-vf") + 1] == "scale=1920:1080"
        assert "-r" in cmd and cmd[cmd.index("-r") + 1] == "30"
        assert "-ss" in cmd and cmd[cmd.index("-ss") + 1] == "00:01:00"
        assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "60"
        assert cmd[-1] == "/tmp/out.mkv"
        assert cmd.index("-i") < cmd.index("-ss")

    def test_unsupported_output_format(self, converter):
        """OUTPUT_FORMATS does not include wmv — validation catches it in convert()."""
        from src.infrastructure.converters.video_converter import VideoConverter

        assert "wmv" not in VideoConverter.OUTPUT_FORMATS

    def test_converter_not_available(self):
        """Converter raises ProcessingError when ffmpeg is missing."""
        from src.infrastructure.converters.video_converter import VideoConverter

        c = VideoConverter()
        c._ffmpeg_path = None

        with pytest.raises(Exception):
            import asyncio

            f = c.convert(
                input_path=Path("/dev/null"),
                output_path=Path("/tmp/out"),
                output_format="mp4",
            )
            asyncio.run(f)


class TestVideoSettingsValidation:
    """Test settings-level format validation."""

    def test_is_video_format_supported_input(self):
        settings = get_settings()
        assert settings.is_video_format_supported("mp4") is True
        assert settings.is_video_format_supported("mkv") is True
        assert settings.is_video_format_supported("webm") is True
        assert settings.is_video_format_supported("exe") is False

    def test_is_video_format_supported_output(self):
        settings = get_settings()
        assert settings.is_video_format_supported("mp4", is_output=True) is True
        assert settings.is_video_format_supported("wmv", is_output=True) is False

    def test_is_format_supported_includes_video(self):
        settings = get_settings()
        assert settings.is_format_supported("mp4") is True
        assert settings.is_format_supported("mkv", is_output=True) is True


class TestProcessVideoHandlerValidation:
    """Test handler-level validation.

    These tests mock the handler's dependencies and verify that
    ProcessVideoHandler raises ValidationError before enqueuing.
    """

    @pytest.fixture
    def mock_job(self):
        job = MagicMock()
        job.can_start_processing.return_value = True
        job.file_id = "file-123"
        return job

    @pytest.fixture
    def handler(self, mock_job):
        from src.application.handlers import ProcessVideoHandler

        repo = AsyncMock()
        repo.get_job.return_value = mock_job

        queue = AsyncMock()
        storage = AsyncMock()
        storage.get_file.return_value = Path("/tmp/test.mp4")

        return ProcessVideoHandler(repo, queue, storage), repo

    async def _call(self, handler, output_format: str, **kwargs):
        from src.application.commands import ProcessVideoCommand

        cmd = ProcessVideoCommand(
            job_id="job-123",
            output_format=output_format,
            **kwargs,
        )
        return await handler.handle(cmd)

    def test_output_equals_input_without_params_raises_error(self, handler):
        """Same format without processing params → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mp4"

        import asyncio

        with pytest.raises(ValidationError, match="must differ"):
            asyncio.run(self._call(h, "mp4"))

    def test_output_equals_input_with_crf_passes(self, handler):
        """Same format with CRF (re-encode) → allowed."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mp4"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp4", crf=28))
        except ValidationError:
            pytest.fail("Same format with CRF should be allowed")
        except Exception:
            pass  # May fail later

    def test_output_equals_input_with_resolution_passes(self, handler):
        """Same format with resolution → allowed."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mp4"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp4", resolution="1280:720"))
        except ValidationError:
            pytest.fail("Same format with resolution should be allowed")
        except Exception:
            pass

    def test_output_equals_input_with_remove_audio_passes(self, handler):
        """Same format with remove_audio → allowed."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mp4"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp4", remove_audio=True))
        except ValidationError:
            pytest.fail("Same format with remove_audio should be allowed")
        except Exception:
            pass

    def test_output_differs_from_input_passes(self, handler):
        """Output format different from input → no error."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp4"))
        except ValidationError:
            pytest.fail("Should not raise ValidationError for different formats")
        except Exception:
            pass  # May fail later (queue, MIME), but not on format check

    def test_crf_out_of_range_raises_error(self, handler):
        """CRF outside 0-51 range → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        with pytest.raises(ValidationError, match="CRF must be between 0 and 51"):
            asyncio.run(self._call(h, "mp4", crf=-1))

        with pytest.raises(ValidationError, match="CRF must be between 0 and 51"):
            asyncio.run(self._call(h, "mp4", crf=52))

    def test_invalid_resolution_format_raises_error(self, handler):
        """Resolution without colon → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        with pytest.raises(ValidationError, match="Invalid resolution"):
            asyncio.run(self._call(h, "mp4", resolution="1920x1080"))

    def test_valid_resolution_passes(self, handler):
        """Valid resolution format → no validation error."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp4", resolution="1920:1080"))
        except ValidationError:
            pytest.fail("Should not raise ValidationError for valid resolution")
        except Exception:
            pass

    def test_extract_and_remove_audio_raises_error(self, handler):
        """extract_audio + remove_audio simultaneously → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        with pytest.raises(ValidationError, match="Cannot extract and remove"):
            asyncio.run(self._call(h, "mp3", extract_audio=True, remove_audio=True))

    def test_extract_audio_with_video_params_raises_error(self, handler):
        """extract_audio with CRF → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        with pytest.raises(ValidationError, match="incompatible"):
            asyncio.run(
                self._call(h, "mp3", extract_audio=True, crf=23)
            )

    def test_invalid_audio_bitrate_format_raises_error(self, handler):
        """Invalid audio bitrate → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        with pytest.raises(ValidationError, match="Invalid audio bitrate"):
            asyncio.run(
                self._call(h, "mp4", extract_audio=True, audio_bitrate="abc")
            )

    def test_valid_audio_bitrate_passes(self, handler):
        """Valid audio bitrate like 192k → no ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "mkv"

        import asyncio

        try:
            asyncio.run(
                self._call(h, "mp4", extract_audio=True, audio_bitrate="192k", audio_output_format="mp3")
            )
        except ValidationError:
            pytest.fail("Should not raise ValidationError for valid bitrate")
        except Exception:
            pass
