# Video Processing Specification

## Purpose

Video format conversion and processing via `POST /api/v1/process/video` using FFmpeg. 10 input formats → 8 output. Async job pattern from document/audio conversion. Fase 1 covers core operations; Fase 2 operations documented in `video-processing-fase2/spec.md`.

## Requirements

### Requirement: Video Format Conversion

The system MUST accept video uploads at `POST /api/v1/process/video` and convert formats using FFmpeg. Input MUST be from the supported list. Output MUST be supported and MUST differ from input. The system SHALL return HTTP 202 with `job_id` on successful queue.

Supported input formats (10): `mp4`, `mkv`, `mov`, `avi`, `webm`, `flv`, `wmv`, `mpeg`, `3gp`, `m4v`
Supported output formats (8): `mp4`, `mkv`, `mov`, `avi`, `webm`, `flv`, `mpeg`, `m4v`

Codec mapping per output format:

| Format | Video Encoder | Audio Encoder |
|--------|--------------|---------------|
| mp4 | libx264 (H.264) | aac |
| mkv | libx264 (H.264) | aac |
| mov | libx264 (H.264) | aac |
| avi | mpeg4 | mp3 |
| webm | libvpx-vp9 | libopus |
| flv | flv | mp3 |
| mpeg | mpeg2video | mp2 |
| m4v | libx264 (H.264) | aac |

#### Scenario: Valid mp4 → mkv conversion

- GIVEN an mp4 file with MIME `video/mp4`
- WHEN POST with `output_format: mkv`
- THEN HTTP 202 with `job_id`
- AND the job SHALL complete with an mkv file

#### Scenario: Unsupported input format

- GIVEN a `.xyz` file (not in supported list)
- WHEN POST `/api/v1/process/video`
- THEN HTTP 400 listing supported formats

#### Scenario: Output equals input format

- GIVEN an mp4 file with `output_format: mp4`
- THEN HTTP 400 "Output format must differ from input format"

### Requirement: Video Compression (CRF)

The system SHOULD accept `crf` (integer 0-51, lower = better quality, default 23) for lossy compression. CRF values below 18 are near-lossless; above 28 are smaller but lower quality.

#### Scenario: Compression with CRF=28

- GIVEN a high-bitrate mp4 file
- WHEN POST with `output_format: mp4, crf: 28`
- THEN output file SHALL be smaller than source (compression applied)
- AND the job SHALL complete successfully

#### Scenario: CRF out of range

- WHEN POST with `crf: -1` or `crf: 60`
- THEN HTTP 400 "CRF must be between 0 and 51"

### Requirement: Resolution Scaling

The system SHOULD accept `resolution` (string `"width:height"`) to scale video dimensions. Supported presets include 1920:1080 (1080p), 1280:720 (720p), 854:480 (480p). Auto-width via `-1:720` is supported.

#### Scenario: Scale to 720p

- GIVEN a 1080p video
- WHEN POST with `resolution: "1280:720"`
- THEN output SHALL be 1280x720 pixels

#### Scenario: Invalid resolution format

- WHEN POST with `resolution: "abc"`
- THEN HTTP 400 "Invalid resolution format"

### Requirement: FPS Adjustment

The system SHOULD accept `fps` (integer) to change frame rate. Common values: 24, 30, 60.

#### Scenario: Change FPS to 30

- GIVEN a 60fps video
- WHEN POST with `fps: 30`
- THEN output SHALL have 30fps

### Requirement: Video Trimming

The system SHOULD accept `trim_start` (string HH:MM:SS) and `trim_duration` (integer seconds) to extract a segment. Seek-after-input for accurate trimming.

#### Scenario: Extract 30s segment

- GIVEN a 5-minute video
- WHEN POST with `trim_start: "00:01:00", trim_duration: 30`
- THEN output SHALL be ~30s starting at 1:00

### Requirement: Audio Extraction

The system SHOULD accept `extract_audio: true` and `audio_output_format` (e.g. `mp3`, `aac`, `wav`, `opus`) to extract audio track as a standalone audio file. Mutually exclusive with `crf`, `resolution`, `fps`, `remove_audio`.

#### Scenario: Extract MP3 from video

- GIVEN a video with audio track
- WHEN POST with `extract_audio: true, audio_output_format: mp3`
- THEN output SHALL be an MP3 file with the video's audio

### Requirement: Audio Removal

The system SHOULD accept `remove_audio: true` to produce a video without an audio track (muted). Mutually exclusive with `extract_audio`.

#### Scenario: Remove audio from video

- GIVEN a video with audio track
- WHEN POST with `remove_audio: true`
- THEN output SHALL be a video file with no audio stream

### Requirement: Input Validation

The system MUST validate MIME types and file size before queuing. Only video MIME types matching supported inputs SHALL be accepted.

#### Scenario: Non-video file

- GIVEN a PDF file
- WHEN POST `/api/v1/process/video`
- THEN HTTP 415 "Unsupported media type for video processing"

### Requirement: Error Handling

The system MUST handle FFmpeg failures: missing FFmpeg → HTTP 503; timeout (900s, configurable) → kill process + fail job; non-zero exit → parse stderr + descriptive error.

#### Scenario: Conversion timeout

- GIVEN a very long video
- WHEN conversion exceeds 900s
- THEN the system SHALL kill the FFmpeg subprocess
- AND fail the job with "Video conversion timed out after 900s"

## Error Summary

| Error | HTTP | Message |
|-------|------|---------|
| Unsupported input | 400 | `Supported: {list}` |
| Output equals input | 400 | Must differ |
| CRF out of range | 400 | Must be between 0 and 51 |
| Invalid resolution | 400 | Invalid resolution format |
| extract_audio + remove_audio conflict | 400 | Cannot extract and remove audio simultaneously |
| extract_audio + video params conflict | 400 | extract_audio is incompatible with video processing params |
| Wrong media type | 415 | Unsupported media type |
| Video file too large | 413 | Exceeds 200MB limit |
| FFmpeg absent | 503 | Video processing unavailable: FFmpeg not found |
| Timeout | 500 | Timed out after 900s |
| Process failure | 500 | Failed: {ffmpeg_stderr} |
