# Audio Processing Specification

## Purpose

Audio format conversion via `POST /api/v1/process/audio` using FFmpeg. 10 input formats → 7 output. Async job pattern from document conversion.

## Requirements

### Requirement: Audio Format Conversion

The system MUST accept audio uploads at `POST /api/v1/process/audio` and convert formats using FFmpeg. Input MUST be from the supported list. Output MUST be supported and MUST differ from input. The system SHALL return HTTP 202 with `job_id` on successful queue.

#### Scenario: Valid mp3 → wav

- GIVEN an mp3 file with MIME `audio/mpeg`
- WHEN POST with `output_format: wav`
- THEN HTTP 202 with `job_id`
- AND the job SHALL complete with a wav file

#### Scenario: Unsupported input format

- GIVEN a `.ra` file (not in supported list)
- WHEN POST `/api/v1/process/audio`
- THEN HTTP 400 listing supported formats

#### Scenario: Output equals input format

- GIVEN a wav file with `output_format: wav`
- THEN HTTP 400 "Output format must differ from input format"

### Requirement: Optional Parameters

The system SHOULD accept: `bitrate` (string), `sample_rate` (int, Hz), `channels` (1 or 2), `trim_start` (float, seconds), `trim_duration` (float, seconds), `normalize_volume` (bool). Validation MUST reject invalid combos before queuing. Volume normalization SHALL use FFmpeg `dynaudnorm` (single-pass).

#### Scenario: Bitrate and sample rate override

- GIVEN a wav file
- WHEN POST with `output_format: mp3, bitrate: "192k", sample_rate: 44100`
- THEN output SHALL be mp3 at 192kbps and 44100Hz

#### Scenario: Invalid bitrate

- WHEN POST with `bitrate: "999k"` for mp3
- THEN HTTP 400 "Invalid bitrate value for output format"

#### Scenario: Volume normalization

- GIVEN a quiet audio file
- WHEN POST with `normalize_volume: true`
- THEN the job SHALL apply `dynaudnorm` FFmpeg filter

#### Scenario: Audio trimming

- GIVEN a 60s audio file
- WHEN POST with `trim_start: 10.0, trim_duration: 30.0`
- THEN output SHALL be ~30s starting at 10s

### Requirement: Input Validation

The system MUST validate MIME types and file size before queuing. Max file size SHALL be 200MB. Only audio MIME types matching supported inputs SHALL be accepted.

#### Scenario: Non-audio file

- GIVEN a PDF file
- WHEN POST `/api/v1/process/audio`
- THEN HTTP 415 "Unsupported media type for audio processing"

#### Scenario: File exceeds size limit

- GIVEN a 250MB audio file
- WHEN POST `/api/v1/process/audio`
- THEN HTTP 413 "File size exceeds maximum of 200MB"

### Requirement: Error Handling and Cleanup

The system MUST handle FFmpeg failures: missing FFmpeg → HTTP 503; timeout (600s, configurable) → kill process + fail job; non-zero exit → parse stderr + descriptive error. On interruption, the system MUST call `process.kill()` then `process.wait()`. Temp files MUST be removed on completion or failure.

#### Scenario: FFmpeg not installed

- GIVEN FFmpeg is absent
- WHEN any audio request arrives
- THEN HTTP 503 "Audio processing unavailable: FFmpeg not found"

#### Scenario: Conversion timeout

- GIVEN a very long audio file
- WHEN conversion exceeds 600s
- THEN the system SHALL kill the FFmpeg subprocess
- AND fail the job with "Audio conversion timed out after 600s"

#### Scenario: Corrupted input file

- GIVEN a corrupted audio file
- WHEN conversion starts
- THEN the job SHALL fail with FFmpeg stderr error

#### Scenario: Kill on timeout

- GIVEN a timed-out conversion
- WHEN the timeout handler triggers
- THEN FFmpeg SHALL be killed and awaited before reporting failure

## Error Summary

| Error | HTTP | Message |
|-------|------|---------|
| Unsupported input | 400 | `Supported: {list}` |
| Output equals input | 400 | Must differ |
| Invalid param | 400 | `Invalid {param}: {reason}` |
| Wrong media type | 415 | Unsupported media type |
| File too large | 413 | Exceeds 200MB limit |
| FFmpeg absent | 503 | FFmpeg not found |
| Timeout | 500 | Timed out after 600s |
| Process failure | 500 | Failed: {ffmpeg_stderr} |
