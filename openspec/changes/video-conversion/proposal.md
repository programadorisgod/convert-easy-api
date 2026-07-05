# Proposal: Video Conversion with FFmpeg

## Intent

Add video format conversion using FFmpeg, following the exact same patterns as audio conversion (AudioConverter, ProcessAudioHandler, worker routing). Fase 1 covers core operations; Fase 2 operations are documented as pending for future implementation.

## Scope

### In Scope
- Format conversion: 10 input → 8 output video formats using FFmpeg
- Compression via CRF (0-51)
- Resolution scaling (width:height)
- FPS adjustment
- Video trimming (start timestamp + duration)
- Audio extraction from video (video → audio file output)
- Audio removal from video (muted output)
- Unit tests for command building, codec mapping, handler validation

### Out of Scope (Fase 2 — documented as pending spec)
- Video joining (concat)
- Audio replacement in video
- GIF creation from video
- Frame extraction / thumbnails
- Rotate / flip
- Watermark overlay
- Codec selection (H.265, VP9, AV1)
- Video metadata via ffprobe
- Bitrate configuration (video/audio bitrate)

## Capabilities

### New Capabilities
- `video-processing`: Video format conversion and processing using FFmpeg. Covers format conversion, compression (CRF), resolution scaling, FPS adjustment, trimming, audio extraction, and audio removal.

### Modified Capabilities
None.

## Approach

Same pattern as audio conversion: ProcessVideoController → ProcessVideoCommand → ProcessVideoHandler → VideoConverter → Worker routing. VideoConverter wraps FFmpeg with asyncio.create_subprocess_exec, builds commands from optional parameters, handles timeout with process.kill() + process.wait(). Singleton via get_video_converter().

Format support:
- Input (10): mp4, mkv, mov, avi, webm, flv, wmv, mpeg, 3gp, m4v
- Output (8): mp4, mkv, mov, avi, webm, flv, mpeg, m4v

Codec mapping: mp4/mkv/mov/m4v→libx264, avi→mpeg4, webm→libvpx-vp9, flv→flv, mpeg→mpeg2video

Settings (new): supported_video_input_formats, supported_video_output_formats, max_video_conversion_time_seconds (900s), is_video_format_supported()

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| shared/config/settings.py | Modified | Video format lists + is_video_format_supported() + update is_format_supported() chain |
| src/infrastructure/mime_validator.py | Modified | Video MIME types + m4v→mp4 alias in _FORMAT_ALIASES |
| src/application/commands.py | Modified | ProcessVideoCommand dataclass |
| src/application/handlers.py | Modified | ProcessVideoHandler with validations |
| src/infrastructure/converters/video_converter.py | New | VideoConverter class mirroring AudioConverter |
| src/infrastructure/converters/__init__.py | Modified | Export VideoConverter, get_video_converter |
| src/interfaces/http/controllers/video_processing_controller.py | New | POST /api/v1/process/video endpoint |
| src/interfaces/http/controllers/__init__.py | Modified | Export video_processing_controller router |
| src/main.py | Modified | Register video_processing_controller.router |
| src/infrastructure/worker/conversion_worker.py | Modified | is_video_job detection + _convert_video() method |
| tests/test_video_converter.py | New | Unit tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FFmpeg build missing libx264/libvpx | Low | Document requirement; current Docker image likely has them |
| Video encoding timeout | Medium | Configurable max_video_conversion_time_seconds (default 900s) |
| m4v MIME detected as mp4 | Low | _FORMAT_ALIASES maps m4v→mp4 for validation |
| extract_audio creates hybrid video→audio path | Low | Separate branching in _build_ffmpeg_command + worker routing |

## Rollback Plan

Revert by removing the video_processing_controller router registration, VideoConverter import, and worker routing. All changes are additive (no existing behavior modified).

## Dependencies

- FFmpeg with libx264, libvpx, and mpeg4 encoders (already in Docker image)

## Success Criteria

- [ ] POST /api/v1/process/video returns 202 with job_id
- [ ] All 8 output formats produce valid video files via integration tests
- [ ] CRF, resolution, FPS, trim params work correctly
- [ ] Extract audio produces valid audio file from video input
- [ ] Remove audio produces video without audio track
- [ ] All unit + integration tests pass
- [ ] 0 new lint/type errors
