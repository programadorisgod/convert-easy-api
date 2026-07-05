# Video Conversion — Technical Design

## Overview

Video conversion using FFmpeg, following AudioConverter pattern exactly. Operations: format conversion, CRF compression, resolution scaling, FPS change, trimming, audio extraction, audio removal.

## Architecture

```
POST /api/v1/process/video
  └─ video_processing_controller (FastAPI)
       └─ ProcessVideoHandler (application use case)
            ├─ validates job state, format, params
            ├─ enqueues job with video_config
            └─ returns 202
                    │
                    ▼ Worker (BullMQ Consumer)
                    └─ _convert_video()
                         └─ VideoConverter
                              ├─ _build_ffmpeg_command()
                              └─ _run_command()
                                   └─ asyncio.create_subprocess_exec(ffmpeg, ...)
```

## Data Flow

### Request → Command

```json
{
  "job_id": "uuid",
  "output_format": "mkv",
  "crf": 23,
  "resolution": "1920:1080",
  "fps": 30,
  "trim_start": "00:01:00",
  "trim_duration": 30,
  "extract_audio": false,
  "audio_output_format": null,
  "remove_audio": false
}
```

### Handler → Job Data

```python
video_config = {
    "output_format": "mkv",
    "crf": 23,
    "resolution": "1920:1080",
    "fps": 30,
    "trim_start": "00:01:00",
    "trim_duration": 30,
    "extract_audio": False,
    "audio_output_format": None,
    "remove_audio": False,
}
job_data = {
    "job_id": "...",
    "file_id": "...",
    "input_format": "mp4",
    "output_format": "mkv",
    "video_config": video_config,
}
```

### Worker Routing

```python
is_video_job = (
    self.settings.is_video_format_supported(input_format)
    and self.settings.is_video_format_supported(output_format, is_output=True)
)
# extract_audio edge case: video input → audio output
is_extract_audio = job_data.get("video_config", {}).get("extract_audio", False) and (
    self.settings.is_audio_format_supported(output_format, is_output=True)
)

# Order: pdf > xml > image > audio > video > document
if is_video_job or is_extract_audio:
    video_config = job_data.get("video_config") or {}
    output_path = await self._convert_video(
        input_path=input_path,
        file_id=file_id,
        output_format=output_format,
        **video_config,
    )
```

## VideoConverter Class Design

```python
class VideoConverter:
    """Converts video files using FFmpeg subprocess.

    Supports format conversion, compression (CRF), resolution scaling,
    FPS adjustment, trimming, audio extraction, and audio removal.
    """

    INPUT_FORMATS = frozenset({
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "wmv", "mpeg", "3gp", "m4v",
    })

    OUTPUT_FORMATS = frozenset({
        "mp4", "mkv", "mov", "avi", "webm",
        "flv", "mpeg", "m4v",
    })

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

    # Audio encoders used when extract_audio=True
    EXTRACT_AUDIO_ENCODERS: dict[str, str] = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "aac": "aac",
        "m4a": "aac",
        "flac": "flac",
        "ogg": "libvorbis",
        "opus": "libopus",
    }
```

### FFmpeg Command Construction

```python
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
    remove_audio: bool = False,
) -> list[str]:
```

Command structure:

```
ffmpeg -y -i {input}
  [-ss {trim_start}] [-t {trim_duration}]
  [-vn -c:a {audio_enc}]  (if extract_audio)
  | OR |
  [-c:v {video_enc}] [-crf {crf}]
  [-vf scale={resolution}]
  [-r {fps}]
  [-an]  (if remove_audio)
  {output_path}.{output_format}
```

### `_run_command()` — Identical to AudioConverter

```python
async def _run_command(self, cmd: list[str]) -> tuple[str, str]:
    """Execute FFmpeg subprocess with timeout."""
    timeout = self.settings.max_video_conversion_time_seconds
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ProcessingError(
            f"Video conversion timed out after {timeout}s"
        )
    if process.returncode != 0:
        raise ProcessingError(
            f"Video conversion failed: {stderr.decode(errors='replace')}"
        )
    return stdout.decode(errors="replace"), stderr.decode(errors="replace")
```

## Validation Rules (in ProcessVideoHandler)

| Check | Error |
|-------|-------|
| `output_format == input_format` | 400 "must differ" |
| `crf` not in 0..51 | 400 "CRF must be between 0 and 51" |
| `resolution` doesn't match `r"^\d+:\d+$"` or `r"^-1:\d+$"` | 400 "Invalid resolution format" |
| `fps` is not positive | 400 "FPS must be positive" |
| `extract_audio` and `remove_audio` both True | 400 "Cannot extract and remove audio simultaneously" |
| `extract_audio` with `crf`/`resolution`/`fps` set | 400 "extract_audio is incompatible with video processing params" |
| `audio_output_format` not in audio output list | 400 "Unsupported audio output format" |

## File Changes Summary

| File | Change |
|------|--------|
| `shared/config/settings.py` | +video format lists, +max_video_conversion_time_seconds, +is_video_format_supported(), update is_format_supported() |
| `src/infrastructure/mime_validator.py` | +10 video MIME types, +m4v→mp4 alias |
| `src/application/commands.py` | +ProcessVideoCommand frozen dataclass |
| `src/application/handlers.py` | +ProcessVideoHandler with validations |
| `src/infrastructure/converters/video_converter.py` | NEW — VideoConverter class |
| `src/infrastructure/converters/__init__.py` | +VideoConverter, get_video_converter exports |
| `src/interfaces/http/controllers/video_processing_controller.py` | NEW — POST /process/video |
| `src/interfaces/http/controllers/__init__.py` | +video_processing_controller export |
| `src/main.py` | +video_processing_controller.router |
| `src/infrastructure/worker/conversion_worker.py` | +is_video_job routing + _convert_video() |
| `tests/test_video_converter.py` | NEW — unit tests |

## Timeout

`max_video_conversion_time_seconds: int = 900` (15 minutes) — video encoding is significantly slower than audio. Configurable via env `MAX_VIDEO_CONVERSION_TIME_SECONDS`.

## Dependencies

- FFmpeg with libx264, libvpx, mpeg4 encoders (already in Docker image)
- No new Python packages
