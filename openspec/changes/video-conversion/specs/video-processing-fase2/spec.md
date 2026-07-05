# Video Processing — Fase 2 (Pending)

> **Status**: PENDING — Not implemented. Planned for future iteration after Fase 1 (core operations) is complete.

## Purpose

Advanced video operations beyond basic conversion and compression. These operations extend `POST /api/v1/process/video` with additional capabilities.

## Pending Operations

### 1. Video Joining (Concat)

Join multiple video files sequentially using FFmpeg concat demuxer.

```
ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4
```

**Dependencies**: Needs multi-video upload workflow (separate job IDs for each segment).

### 2. Audio Replacement

Replace video audio track with an external audio file.

```
ffmpeg -i video.mp4 -i audio.mp3 -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4
```

**Dependencies**: Needs separate audio upload or reference to previous job.

### 3. GIF Creation

Convert video segment to animated GIF.

```
ffmpeg -i input.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" -c:v gif output.gif
```

**No new dependencies** — pure FFmpeg.

### 4. Frame Extraction

Extract video frames as PNG images.

```
ffmpeg -i input.mp4 -vf "fps=1" frame_%04d.png
```

**Dependencies**: Needs multi-file output handling in worker.

### 5. Thumbnail Generation

Generate a single thumbnail image from a video timestamp.

```
ffmpeg -ss 00:00:10 -i input.mp4 -frames:v 1 thumbnail.jpg
```

**No new dependencies** — single image output, follows existing patterns.

### 6. Rotate

Rotate video 90°, 180°, or 270°.

```
ffmpeg -i input.mp4 -vf "transpose=1" output.mp4   # 90° clockwise
ffmpeg -i input.mp4 -vf "transpose=2" output.mp4   # 90° counter-clockwise
ffmpeg -i input.mp4 -vf "transpose=3" output.mp4   # 180°
```

**No new dependencies**.

### 7. Flip

Flip video horizontally or vertically.

```
ffmpeg -i input.mp4 -vf "hflip" output.mp4   # horizontal
ffmpeg -i input.mp4 -vf "vflip" output.mp4   # vertical
```

**No new dependencies**.

### 8. Watermark Overlay

Overlay image (PNG) or text watermark on video.

```
ffmpeg -i input.mp4 -i logo.png -filter_complex "overlay=10:10" output.mp4
```

**Dependencies**: Needs watermark image upload or text parameter. Follows existing watermark service patterns from image processing.

### 9. Codec Selection

Allow user to select video codec (H.264, H.265, VP9, AV1) and audio codec (AAC, MP3, Opus).

```
ffmpeg -i input.mp4 -c:v libx265 -c:a libopus output.mkv
```

**No new dependencies** — extends existing codec mapping.

### 10. Bitrate Configuration

Allow user to set video bitrate (1M, 2M, 5M, 10M) and audio bitrate (128k, 192k, 320k).

**No new dependencies**.

### 11. Video Metadata (ffprobe)

Return video metadata (duration, resolution, fps, codec, bitrate, audio channels) using ffprobe.

```
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4
```

**Dependencies**: New endpoint or return field, ffprobe binary (included with FFmpeg).

## Priority Order (Recommended)

| Priority | Operation | Complexity | Deps |
|----------|-----------|------------|------|
| 1 | Thumbnail generation | Low | None |
| 2 | Codec selection | Low | None |
| 3 | Bitrate configuration | Low | None |
| 4 | Rotate / Flip | Low | None |
| 5 | Frame extraction | Medium | Multi-file output |
| 6 | GIF creation | Medium | None |
| 7 | Watermark overlay | Medium | Image upload |
| 8 | Audio replacement | High | Multi-job ref |
| 9 | Video joining | High | Multi-job ref |
| 10 | ffprobe metadata | Medium | ffprobe binary |

## Notes for Implementation

- Each operation should be added as an optional parameter to `ProcessVideoCommand`, similar to how `extract_audio` and `remove_audio` work.
- Operations that need multiple input files (join, replace audio) will require extending the upload workflow first.
- Watermark can reuse image upload patterns from watermark_service.py.
