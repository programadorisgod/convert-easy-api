"""CLI commands for Base64 image encoding and decoding."""

import base64
import binascii
from pathlib import Path
from typing import Annotated

import typer

from src.interfaces.cli.ui import console, format_file_size, print_error, print_success
from src.interfaces.http.controllers.base64_controller import _extension_to_mime, _strip_data_uri

app = typer.Typer(
    name="base64",
    help="Image to Base64 (or Data URI) encoding and decoding.",
    no_args_is_help=True,
)


@app.command("encode")
def encode_image(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source image.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional file path to save the base64 string. If omitted, prints to console.",
        ),
    ] = None,
    data_uri: Annotated[
        bool,
        typer.Option(
            "--data-uri/--raw",
            help="Output as full Data URI (data:image/png;base64,...) or raw base64 string.",
        ),
    ] = True,
) -> None:
    """Encode an image file into a Base64 string or Data URI."""
    try:
        raw_bytes = input_file.read_bytes()
        mime = _extension_to_mime(input_file.name)
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        result = f"data:{mime};base64,{b64_str}" if data_uri else b64_str

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(result, encoding="utf-8")
            print_success(
                f"Encoded [bold]{input_file.name}[/bold] to {output} ({format_file_size(len(result))}).",
                title="Base64 Encoded",
            )
        else:
            console.print(result)
    except Exception as e:
        print_error(f"Failed to encode image to base64: {e}")
        raise typer.Exit(code=1)


@app.command("decode")
def decode_base64(
    input_data: Annotated[
        str,
        typer.Argument(
            help="Base64 string, Data URI, or path to a text file containing base64 data.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination image file path (e.g. output.png).",
        ),
    ],
) -> None:
    """Decode a Base64 string or Data URI back into an image file."""
    try:
        # Check if argument is a file path
        possible_file = Path(input_data)
        if possible_file.is_file():
            content = possible_file.read_text(encoding="utf-8")
        else:
            content = input_data

        clean_b64, mime = _strip_data_uri(content)
        raw_bytes = base64.b64decode(clean_b64, validate=True)

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw_bytes)

        print_success(
            f"Decoded image successfully ({format_file_size(len(raw_bytes))}).\n"
            f"Saved to: [underline]{output}[/underline]",
            title="Base64 Decoded",
        )
    except (binascii.Error, ValueError) as e:
        print_error(f"Invalid Base64 payload: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to decode base64: {e}")
        raise typer.Exit(code=1)
