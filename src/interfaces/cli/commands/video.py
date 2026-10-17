"""CLI commands for video conversion and manipulation using FFmpeg."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.video_converter import get_video_converter
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="video",
    help="Video conversion, compression (CRF), resizing, FPS, audio extraction and trimming.",
    no_args_is_help=True,
)


@app.command("convert")
def convert_video(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source video file.",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Target format (mp4, webm, mkv, mov, avi, flv, gif, mpeg, m4v, ts).",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output path. If omitted, saves next to input file.",
        ),
    ] = None,
    crf: Annotated[
        int | None,
        typer.Option(
            "--crf",
            min=0,
            max=51,
            help="CRF quality value (0-51, lower = higher quality, default 23).",
        ),
    ] = None,
    resolution: Annotated[
        str | None,
        typer.Option(
            "--resolution",
            "-r",
            help="Resolution as WIDTH:HEIGHT (e.g. '1920:1080', '1280:720', or '-1:480').",
        ),
    ] = None,
    fps: Annotated[
        int | None,
        typer.Option(
            "--fps",
            min=1,
            help="Target framerate (e.g. 24, 30, 60).",
        ),
    ] = None,
    trim_start: Annotated[
        str | None,
        typer.Option(
            "--trim-start",
            help="Trim start timestamp (HH:MM:SS or seconds).",
        ),
    ] = None,
    trim_duration: Annotated[
        int | None,
        typer.Option(
            "--trim-duration",
            help="Trim duration in seconds.",
        ),
    ] = None,
    mute: Annotated[
        bool,
        typer.Option(
            "--mute",
            help="Remove audio track from output video.",
        ),
    ] = False,
) -> None:
    """Convert video format with resolution, FPS, quality, and trimming controls."""
    out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting video [yellow]{input_file.name}[/yellow] to [green]{format.upper()}[/green]..."):
        try:
            converter = get_video_converter()
            asyncio.run(
                converter.convert(
                    input_path=input_file,
                    output_path=out_path,
                    output_format=format.lower(),
                    crf=crf,
                    resolution=resolution,
                    fps=fps,
                    trim_start=trim_start,
                    trim_duration=trim_duration,
                    remove_audio=mute,
                )
            )
        except Exception as e:
            print_error(f"Failed to convert video: {e}")
            raise typer.Exit(code=1)

    in_size = input_file.stat().st_size
    out_size = out_path.stat().st_size

    print_success(
        f"Converted: [bold]{input_file.name}[/bold] ({format_file_size(in_size)}) ➔ "
        f"[bold]{out_path.name}[/bold] ({format_file_size(out_size)})\n"
        f"Saved to: [underline]{out_path}[/underline]",
        title="Video Converted",
    )


@app.command("extract-audio")
def extract_audio(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source video file.",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Audio format to extract (mp3, wav, aac, flac, ogg, opus, m4a).",
        ),
    ] = "mp3",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output audio path. Defaults to [video_stem].[format].",
        ),
    ] = None,
    bitrate: Annotated[
        str | None,
        typer.Option(
            "--bitrate",
            "-b",
            help="Audio bitrate (e.g. 192k, 256k, 320k).",
        ),
    ] = "192k",
) -> None:
    """Extract the audio track from a video file."""
    out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Extracting audio from [yellow]{input_file.name}[/yellow]..."):
        try:
            converter = get_video_converter()
            asyncio.run(
                converter.convert(
                    input_path=input_file,
                    output_path=out_path,
                    output_format=format.lower(),
                    extract_audio=True,
                    audio_output_format=format.lower(),
                    audio_bitrate=bitrate,
                )
            )
        except Exception as e:
            print_error(f"Failed to extract audio: {e}")
            raise typer.Exit(code=1)

    out_size = out_path.stat().st_size
    print_success(
        f"Audio extracted ({format_file_size(out_size)}).\nSaved to: [underline]{out_path}[/underline]",
        title="Audio Extracted",
    )
