"""CLI commands for audio conversion and manipulation using FFmpeg."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.audio_converter import get_audio_converter
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="audio",
    help="Audio conversion, volume normalization, bitrate/sample rate adjustments and trimming.",
    no_args_is_help=True,
)


@app.command("convert")
def convert_audio(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source audio file.",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Target format (mp3, wav, flac, ogg, opus, aac, m4a, wma, ac3, aiff).",
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
    bitrate: Annotated[
        str | None,
        typer.Option(
            "--bitrate",
            "-b",
            help="Audio bitrate: 128k, 192k, 256k, 320k.",
        ),
    ] = None,
    sample_rate: Annotated[
        int | None,
        typer.Option(
            "--sample-rate",
            "-s",
            help="Sample rate in Hz (e.g. 22050, 44100, 48000).",
        ),
    ] = None,
    channels: Annotated[
        int | None,
        typer.Option(
            "--channels",
            "-c",
            help="Channel count: 1 (mono) or 2 (stereo).",
        ),
    ] = None,
    normalize: Annotated[
        bool,
        typer.Option(
            "--normalize/--no-normalize",
            help="Apply dynamic volume normalization (EBU R128).",
        ),
    ] = False,
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
) -> None:
    """Convert audio format with quality, channel, and normalization options."""
    out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting audio [yellow]{input_file.name}[/yellow] to [green]{format.upper()}[/green]..."):
        try:
            converter = get_audio_converter()
            asyncio.run(
                converter.convert(
                    input_path=input_file,
                    output_path=out_path,
                    output_format=format.lower(),
                    bitrate=bitrate,
                    sample_rate=sample_rate,
                    channels=channels,
                    normalize_volume=normalize,
                    trim_start=trim_start,
                    trim_duration=trim_duration,
                )
            )
        except Exception as e:
            print_error(f"Failed to convert audio: {e}")
            raise typer.Exit(code=1)

    in_size = input_file.stat().st_size
    out_size = out_path.stat().st_size

    print_success(
        f"Converted: [bold]{input_file.name}[/bold] ({format_file_size(in_size)}) ➔ "
        f"[bold]{out_path.name}[/bold] ({format_file_size(out_size)})\n"
        f"Saved to: [underline]{out_path}[/underline]",
        title="Audio Converted",
    )
