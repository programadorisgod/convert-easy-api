# Tasks: Video Conversion with FFmpeg

## Task 1: Settings — Add video format lists
**Files**: `shared/config/settings.py`
**Changes**:
- Add `supported_video_input_formats: list[str]` (10 formats)
- Add `supported_video_output_formats: list[str]` (8 formats)
- Add `max_video_conversion_time_seconds: int = 900`
- Add `is_video_format_supported()` method
- Update `is_format_supported()` chain to include video

## Task 2: MIME validator — Add video MIME types
**Files**: `src/infrastructure/mime_validator.py`
**Changes**:
- Add 10 video MIME type mappings to `_MIME_TO_FORMAT`
- Add `"m4v": "mp4"` to `_FORMAT_ALIASES` (libmagic detects m4v as video/mp4)

## Task 3: Commands — Add ProcessVideoCommand
**Files**: `src/application/commands.py`
**Changes**:
- Add `ProcessVideoCommand` frozen dataclass
- Fields: job_id, output_format, crf (opt), resolution (opt), fps (opt), trim_start (opt), trim_duration (opt), extract_audio (bool), audio_output_format (opt), remove_audio (bool)

## Task 4: VideoConverter — Class + FFmpeg command building
**Files**: `src/infrastructure/converters/video_converter.py` (NEW)
**Changes**:
- `VideoConverter` class with `INPUT_FORMATS`, `OUTPUT_FORMATS`, `VIDEO_ENCODERS`, `EXTRACT_AUDIO_ENCODERS`
- `_build_ffmpeg_command()` with 3 branching paths:
  - `extract_audio=True`: `-vn -c:a {audio_enc}`
  - `remove_audio=True`: `-c:v {video_enc}` params + `-an`
  - Normal: `-c:v {video_enc}` + optional CRF/resolution/fps
- Singleton `get_video_converter()`

## Task 5: VideoConverter — convert() + _run_command()
**Files**: `src/infrastructure/converters/video_converter.py`
**Changes**:
- `convert()` async method: validate format → check ffmpeg → build cmd → run → return path
- `_run_command()` async: subprocess with 900s timeout, kill on timeout, stderr parsing
- Handle format normalization (lowercase, strip leading dot)

## Task 6: Handler — Add ProcessVideoHandler
**Files**: `src/application/handlers.py`
**Changes**:
- `ProcessVideoHandler` class with repository, queue, storage
- `handle()` method with validations:
  - Output differs from input
  - CRF 0-51 if provided
  - Resolution format matches `\d+:\d+` or `-1:\d+`
  - FPS positive if provided
  - extract_audio + remove_audio mutual exclusion
  - extract_audio incompatible with crf/resolution/fps
  - audio_output_format valid for extraction
- MIME validation before enqueue
- Build `video_config` dict + `job_data` and enqueue

## Task 7: Controller — POST /process/video endpoint
**Files**: `src/interfaces/http/controllers/video_processing_controller.py` (NEW)
**Changes**:
- `ProcessVideoRequest` Pydantic model with all fields
- `ProcessVideoResponse` model
- `POST /process/video` endpoint returning 202
- Exception handling for JobNotFoundError, ValidationError

## Task 8: Worker — Video routing + _convert_video()
**Files**: `src/infrastructure/worker/conversion_worker.py`
**Changes**:
- Import `get_video_converter`
- Add `is_video_job` detection (check input AND output are video formats)
- Add `is_extract_audio` edge case (video input → audio output)
- Route to `_convert_video()` before document fallback
- Add `_convert_video()` async method (mirrors `_convert_audio`)

## Task 9: Init exports + main registration
**Files**:
- `src/infrastructure/converters/__init__.py` — export `VideoConverter`, `get_video_converter`
- `src/interfaces/http/controllers/__init__.py` — export `video_processing_controller`
- `src/main.py` — `app.include_router(video_processing_controller.router)`

## Task 10: Tests — Unit tests
**Files**: `tests/test_video_converter.py` (NEW)
**Changes**:
- Test codec mapping: all output formats have encoders
- Test format lists: match settings
- Test command building: basic, CRF, resolution, FPS, trim, extract_audio, remove_audio, all combined
- Test handler validation: output equals input, CRF out of range, invalid resolution, extract+remove conflict, valid bitrate for audio extraction
- Test converter not available

## Task 11: Integration tests (if ffmpeg available)
**Files**: `tests/test_video_integration.py` (NEW)
**Changes**:
- Generate small synthetic video with FFmpeg
- Test basic conversion (mp4 → mkv)
- Test CRF compression
- Test resolution scaling
- Test FPS change
- Test extract audio
- Test remove audio
- Test unsupported output format raises error
