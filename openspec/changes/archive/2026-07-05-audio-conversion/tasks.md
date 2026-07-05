# Tasks: audio-conversion

## Phase 1: Foundation (Settings + Validation)

- [x] 1.1 Settings — Add `supported_audio_input_formats`, `supported_audio_output_formats`, `max_audio_conversion_time_seconds`, `is_audio_format_supported()`, update `is_format_supported()`
- [x] 1.2 MIME Validator — Add audio MIME types to `_MIME_TO_FORMAT`
- [x] 1.3 Docker — Add `ffmpeg` to Containerfile and Dockerfile apt-get install

## Phase 2: Command + Converter

- [x] 2.1 Command — Add `ProcessAudioCommand` frozen dataclass to commands.py
- [x] 2.2 Converter — Create `AudioConverter` class in `src/infrastructure/converters/audio_converter.py` with ffmpeg subprocess

## Phase 3: Handler + Controller

- [x] 3.1 Handler — Add `ProcessAudioHandler` to handlers.py
- [x] 3.2 Controller — Create `POST /process/audio` endpoint in `audio_processing_controller.py`

## Phase 4: Worker + Wiring

- [x] 4.1 Worker — Add audio routing to `conversion_worker.py` (check `is_audio_format_supported` + `_convert_audio()`)
- [x] 4.2 Init files — Export `AudioConverter`/`get_audio_converter` and `audio_processing_controller`
- [x] 4.3 Main — Register audio router in `main.py`

## Phase 5: Tests

- [ ] 5.1 Unit tests — AudioConverter command construction, codec mapping, error handling
- [ ] 5.2 Unit tests — ProcessAudioHandler validation, settings format lists
- [ ] 5.3 Integration test — Real ffmpeg conversion (marked with `@pytest.mark.integration`)

## Review Workload Forecast

- Estimated changed lines: ~350-450
- 400-line budget risk: Low-Medium
- Chained PRs recommended: No
- Decision needed before apply: No
