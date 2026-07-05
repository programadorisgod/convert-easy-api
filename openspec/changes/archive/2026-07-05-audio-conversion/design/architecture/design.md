# Design: Audio Conversion with FFmpeg

## Technical Approach

Replicate the `DocumentConverter` pattern exactly: controller → handler → worker → converter, using `asyncio.create_subprocess_exec("ffmpeg")` for the actual conversion. Audio gets its own converter class, its own command + handler, and a routing branch in `_process_job()`.

## Architecture Decisions

### Decision: AudioConverter as a standalone class (not a DocumentConverter mixin)

| Option | Tradeoff |
|--------|----------|
| New `AudioConverter` class | Duplicates `_run_command` (40 lines), but keeps ffmpeg logic isolated from pandoc/libreoffice |
| Add audio methods to `DocumentConverter` | Wrong abstraction — ffmpeg has nothing in common with pandoc |
| Base converter class | Premature abstraction for two converters |

**Decision**: New `AudioConverter` in `src/infrastructure/converters/audio_converter.py`. Singleton via `get_audio_converter()`. The `_run_command` 40-line copy is acceptable — same timeout/kill/stderr pattern but with its own timeout setting.

### Decision: Native AAC encoder (not libfdk_aac)

| Option | Tradeoff |
|--------|----------|
| Native `aac` encoder | Ships with ffmpeg, no license issues, quality is good enough |
| `libfdk_aac` | Better quality but requires non-free ffmpeg build |

**Decision**: Use native `aac` encoder. Edge-case quality difference isn't worth licensing complexity.

### Decision: Worker routing via `audio_config` key (same pattern as document/pdf/xml)

| Option | Tradeoff |
|--------|----------|
| Key-based (`audio_config`) | Consistent with `document_config`, `pdf_config`, `xml_config` pattern |
| Format-list check | Works but inconsistent with existing dispatch pattern |

**Decision**: `if audio_config:` branch in `_process_job()`, after the image/document checks (see data flow).

## Data Flow

```
POST /api/v1/process/audio
  │
  ▼
AudioProcessingController.validate()     ← validates params inline
  │
  ▼
ProcessAudioHandler.handle()             ← builds ProcessAudioCommand, enqueues
  │
  ▼
BullMQ queue (same "easy-convert-jobs")
  │
  ▼
ConversionWorker._process_job()
  │  ┌─ is_image_job?  → image path
  │  ├─ pdf_config?     → PDF path
  │  ├─ xml_config?     → XML path
  │  ├─ audio_config?   → AUDIO path    ◄── NEW
  │  └─ else            → document path
  │
  ▼
_convert_audio()
  │
  ▼
AudioConverter.convert()
  │  shutil.which("ffmpeg") → 503 if absent
  │  _build_ffmpeg_cmd()   → constructs [ffmpeg, -i, in, ...args, out]
  │  _run_command()         → asyncio.create_subprocess_exec
  │                          timeout → kill+wait → ProcessingError
  │                          non-zero → parse stderr → ProcessingError
  ▼
output_path (extensionless, same _get_output_path pattern)
```

## FFmpeg Command Construction

```python
# _build_ffmpeg_cmd builds exactly this structure:
cmd = [
    self._ffmpeg_path,
    "-y",                       # overwrite output
    "-i", str(input_path),      # input file
]

# Codec map (output extension → encoder name):
codec_map = {
    "mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
    "m4a": "aac", "flac": "flac", "ogg": "libvorbis", "opus": "libopus",
}

# Optional params appended in order:
if bitrate:          cmd += ["-b:a", bitrate]
if sample_rate:      cmd += ["-ar", str(sample_rate)]
if channels:         cmd += ["-ac", str(channels)]
if trim_start:       cmd += ["-ss", str(trim_start)]
if trim_duration:    cmd += ["-t", str(trim_duration)]

# Filter chain: normalize_volume adds dynaudnorm
filter_parts = []
if normalize_volume:
    filter_parts.append("dynaudnorm")
if filter_parts:
    cmd += ["-af", ",".join(filter_parts)]

cmd.append(str(output_path))
```

The ffmpeg binary is resolved once in `__init__` via `shutil.which("ffmpeg")`. If absent, `convert()` raises `ProcessingError("Audio processing unavailable: FFmpeg not found")` → HTTP 503 via the handler translating it.

## Error Handling

| Scenario | Mechanism | Result |
|----------|-----------|--------|
| ffmpeg not found | `shutil.which` in `__init__`, checked each `convert()` | ProcessingError → 503 |
| Timeout (600s default) | `asyncio.wait_for` on `process.communicate()` | `process.kill()` + `process.wait()`, then ProcessingError |
| Non-zero exit | Check `process.returncode` | ProcessingError with stderr text |
| Stale temp files | Same cleanup as doc converter — output_path in storage handles it |

The `_run_command` method is a direct copy of `DocumentConverter._run_command` (lines 391–420), parameterized with `self.settings.max_audio_conversion_time_seconds`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/infrastructure/converters/audio_converter.py` | Create | AudioConverter class with ffmpeg subprocess |
| `src/interfaces/http/controllers/audio_processing_controller.py` | Create | POST /process/audio endpoint |
| `shared/config/settings.py` | Modify | Audio format lists + metadata DTO |
| `src/infrastructure/mime_validator.py` | Modify | Audio MIME types in `_MIME_TO_FORMAT` |
| `src/application/commands.py` | Modify | `ProcessAudioCommand` dataclass |
| `src/application/handlers.py` | Modify | `ProcessAudioHandler` class |
| `src/infrastructure/worker/conversion_worker.py` | Modify | `audio_config` routing + `_convert_audio()` |
| `src/main.py` | Modify | Import + register audio router |
| `src/infrastructure/converters/__init__.py` | Modify | Export `AudioConverter` + `get_audio_converter` |
| `src/interfaces/http/controllers/__init__.py` | Modify | Export audio controller module |

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class ProcessAudioCommand:
    job_id: str
    output_format: str
    bitrate: str | None = None        # e.g. "192k"
    sample_rate: int | None = None    # Hz
    channels: int | None = None       # 1 or 2
    trim_start: float | None = None   # seconds
    trim_duration: float | None = None
    normalize_volume: bool = False
```

The `audio_config` dict in job data mirrors this shape, serialized. The `AudioConverter.convert()` signature takes `input_path, output_path, output_format, **params`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Cmd construction | Input → expected `cmd` list (mock ffmpeg binary) |
| Unit | Codec mapping | Each output format → expected encoder name |
| Unit | Error handling | Timeout raises ProcessingError, non-zero exit parses stderr |
| Integration | Full convert | Real ffmpeg, small audio file, verify output exists + correct format |
| E2E | Upload + convert | POST audio → poll job → download result |

## Migration / Rollout

No migration required. New endpoint + handler + converter — no existing code changes beyond the additions listed above. No feature flags.

## Open Questions

- [ ] Confirm `max_file_size_mb` (currently 100MB, spec says 200MB for audio — update settings override?)
- [ ] FFmpeg installed in production image? (needs Dockerfile update if not)
