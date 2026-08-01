"""Unit tests for AudioConverter.

Tests command construction, codec mapping, handler validation,
and error handling without calling FFmpeg (unit scope).
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.config import get_settings
from shared.exceptions import UnsupportedFormatError, ValidationError


# We test the building blocks directly by constructing commands
# the same way AudioConverter does, using its constants.


class TestAudioConverterCodecMapping:
    """Verify codec mapping for each output format."""

    # Expected encoder per format: source of truth from audio_converter.py
    EXPECTED_ENCODERS = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "aac": "aac",
        "m4a": "aac",
        "flac": "flac",
        "ogg": "libvorbis",
        "opus": "libopus",
    }

    def test_all_output_formats_have_encoders(self):
        """Every supported output format must have a codec mapping."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        assert AudioConverter.OUTPUT_FORMATS == set(self.EXPECTED_ENCODERS.keys())

    def test_encoder_mapping_matches(self):
        """Each format maps to the expected FFmpeg encoder."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        for fmt, expected_encoder in self.EXPECTED_ENCODERS.items():
            assert AudioConverter.AUDIO_ENCODERS[fmt] == expected_encoder


class TestAudioConverterInputFormats:
    """Verify input format list."""

    EXPECTED_INPUTS = {
        "mp3", "wav", "aac", "m4a", "flac",
        "ogg", "opus", "wma", "aiff", "amr",
    }

    def test_input_formats_match_settings(self):
        """AudioConverter input formats should match settings list."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        settings = get_settings()
        assert AudioConverter.INPUT_FORMATS == set(settings.supported_audio_input_formats)

    def test_input_formats_contain_all_expected(self):
        from src.infrastructure.converters.audio_converter import AudioConverter

        assert AudioConverter.INPUT_FORMATS == self.EXPECTED_INPUTS


class TestAudioConverterOutputFormats:
    """Verify output format list."""

    EXPECTED_OUTPUTS = {
        "mp3", "wav", "aac", "m4a", "flac", "ogg", "opus",
    }

    def test_output_formats_match_settings(self):
        """AudioConverter output formats should match settings list."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        settings = get_settings()
        assert AudioConverter.OUTPUT_FORMATS == set(settings.supported_audio_output_formats)

    def test_output_formats_contain_all_expected(self):
        from src.infrastructure.converters.audio_converter import AudioConverter

        assert AudioConverter.OUTPUT_FORMATS == self.EXPECTED_OUTPUTS


class TestAudioConverterCommandBuilding:
    """Test FFmpeg command construction via _build_ffmpeg_command.

    These tests instantiate AudioConverter but only test the
    command-building logic — no subprocess is executed.
    """

    @pytest.fixture
    def converter(self):
        """Fixture that patches ffmpeg path to avoid 'not installed' errors."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        c = AudioConverter()
        c._ffmpeg_path = "/usr/bin/ffmpeg"  # Fake path, never executed
        return c

    def test_basic_conversion_command(self, converter):
        """Simple mp3→wav should include input, output, and wav encoder."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/out"),
            output_format="wav",
        )
        assert "/usr/bin/ffmpeg" in cmd
        assert "-y" in cmd
        assert "-i" in cmd
        input_idx = cmd.index("-i")
        assert cmd[input_idx + 1] == "/tmp/test.mp3"
        assert cmd[-1] == "/tmp/out.wav"
        assert "-c:a" in cmd
        c_idx = cmd.index("-c:a")
        assert cmd[c_idx + 1] == "pcm_s16le"

    def test_bitrate_option(self, converter):
        """Bitrate option adds -b:a with value."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp3"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            bitrate="192k",
        )
        assert "-b:a" in cmd
        ba_idx = cmd.index("-b:a")
        assert cmd[ba_idx + 1] == "192k"

    def test_sample_rate_option(self, converter):
        """Sample rate option adds -ar with value."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp3"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            sample_rate=44100,
        )
        assert "-ar" in cmd
        ar_idx = cmd.index("-ar")
        assert cmd[ar_idx + 1] == "44100"

    def test_channels_option(self, converter):
        """Channels option adds -ac with value."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp3"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            channels=1,
        )
        assert "-ac" in cmd
        ac_idx = cmd.index("-ac")
        assert cmd[ac_idx + 1] == "1"

    def test_trim_start_and_duration(self, converter):
        """Trim options add -ss and -t after input."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp3"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            trim_start="00:01:30",
            trim_duration=30,
        )
        assert "-ss" in cmd
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "00:01:30"
        assert "-t" in cmd
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "30"

    def test_normalize_volume(self, converter):
        """Volume normalization adds -af dynaudnorm."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.mp3"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            normalize_volume=True,
        )
        assert "-af" in cmd
        af_idx = cmd.index("-af")
        assert cmd[af_idx + 1] == "dynaudnorm"

    def test_all_options_together(self, converter):
        """All options combined produce a valid command."""
        cmd = converter._build_ffmpeg_command(
            input_path=Path("/tmp/in.flac"),
            output_path=Path("/tmp/out"),
            output_format="mp3",
            bitrate="320k",
            sample_rate=48000,
            channels=2,
            trim_start="00:00:10",
            trim_duration=60,
            normalize_volume=True,
        )
        # Verify each option is present
        assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "320k"
        assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "48000"
        assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "2"
        assert "-ss" in cmd and cmd[cmd.index("-ss") + 1] == "00:00:10"
        assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "60"
        assert "-af" in cmd and cmd[cmd.index("-af") + 1] == "dynaudnorm"
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "libmp3lame"
        assert cmd[-1] == "/tmp/out.mp3"
        # -i should be before -ss (accurate seeking)
        assert cmd.index("-i") < cmd.index("-ss")

    def test_unsupported_output_format(self, converter):
        """OUTPUT_FORMATS does not include wma — validation catches it in convert()."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        assert "wma" not in AudioConverter.OUTPUT_FORMATS

    def test_converter_not_available(self):
        """Converter raises ProcessingError when ffmpeg is missing."""
        from src.infrastructure.converters.audio_converter import AudioConverter

        c = AudioConverter()
        c._ffmpeg_path = None  # Simulate missing ffmpeg

        with pytest.raises(Exception):
            # convert should fail validation before calling subprocess
            import asyncio
            f = c.convert(
                input_path=Path("/dev/null"),
                output_path=Path("/tmp/out"),
                output_format="mp3",
            )
            asyncio.run(f)


class TestAudioSettingsValidation:
    """Test settings-level format validation."""

    def test_is_audio_format_supported_input(self):
        settings = get_settings()
        assert settings.is_audio_format_supported("mp3") is True
        assert settings.is_audio_format_supported("wav") is True
        assert settings.is_audio_format_supported("flac") is True
        assert settings.is_audio_format_supported("exe") is False

    def test_is_audio_format_supported_output(self):
        settings = get_settings()
        assert settings.is_audio_format_supported("mp3", is_output=True) is True
        assert settings.is_audio_format_supported("wma", is_output=True) is False

    def test_is_format_supported_includes_audio(self):
        settings = get_settings()
        assert settings.is_format_supported("mp3") is True
        assert settings.is_format_supported("wav", is_output=True) is True


class TestProcessAudioHandlerValidation:
    """Test handler-level validation (output-equals-input, bitrate format).

    These tests mock the handler's dependencies and verify that
    ProcessAudioHandler raises ValidationError before enqueuing.
    """

    @pytest.fixture
    def mock_job(self):
        job = MagicMock()
        job.can_start_processing.return_value = True
        job.file_id = "file-123"
        return job

    @pytest.fixture
    def handler(self, mock_job):
        from src.application.handlers import ProcessAudioHandler

        repo = AsyncMock()
        repo.get_job.return_value = mock_job

        queue = AsyncMock()
        storage = AsyncMock()
        storage.get_file.return_value = Path("/tmp/test.wav")

        return ProcessAudioHandler(repo, queue, storage), repo

    async def _call(self, handler, output_format: str, bitrate: str | None = None):
        from src.application.commands import ProcessAudioCommand

        cmd = ProcessAudioCommand(
            job_id="job-123",
            output_format=output_format,
            bitrate=bitrate,
        )
        return await handler.handle(cmd)

    def test_output_equals_input_raises_error(self, handler):
        """Output format same as input format → ValidationError."""
        h, repo = handler
        # Mock job.input_format to match the output
        repo.get_job.return_value.input_format = "mp3"

        import asyncio

        with pytest.raises(ValidationError, match="must differ"):
            asyncio.run(self._call(h, "mp3"))

    def test_output_differs_from_input_passes(self, handler):
        """Output format different from input → no error."""
        h, repo = handler
        repo.get_job.return_value.input_format = "wav"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp3"))
        except ValidationError:
            pytest.fail("Should not raise ValidationError for different formats")
        except Exception:
            pass  # May fail later (queue, MIME), but not on format check

    def test_invalid_bitrate_format_raises_error(self, handler):
        """Bitrate with non-digit chars before suffix → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "wav"

        import asyncio

        with pytest.raises(ValidationError, match="Invalid bitrate"):
            asyncio.run(self._call(h, "mp3", bitrate="abc"))

    def test_bitrate_without_suffix_raises_error(self, handler):
        """Bitrate missing k/M suffix → ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "wav"

        import asyncio

        with pytest.raises(ValidationError, match="Invalid bitrate"):
            asyncio.run(self._call(h, "mp3", bitrate="192"))

    def test_valid_bitrate_passes_validation(self, handler):
        """Valid bitrate like 192k → no ValidationError."""
        h, repo = handler
        repo.get_job.return_value.input_format = "wav"

        import asyncio

        try:
            asyncio.run(self._call(h, "mp3", bitrate="192k"))
        except ValidationError:
            pytest.fail("Should not raise ValidationError for valid bitrate")
        except Exception:
            pass  # May fail later
