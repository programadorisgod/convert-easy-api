"""CLI commands for document conversions (pandoc/libreoffice)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.document_converter import get_document_converter
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="doc",
    help="Document conversion between PDF, DOCX, ODT, HTML, Markdown, EPUB, TXT, LaTeX, etc.",
    no_args_is_help=True,
)


@app.command("convert")
def convert_document(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the source document.",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Target format (e.g. pdf, docx, odt, html, md, txt, epub, latex).",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path or destination directory. If omitted, saves next to input file.",
        ),
    ] = None,
    engine: Annotated[
        str,
        typer.Option(
            "--engine",
            "-e",
            help="Engine selection: auto, pandoc, or libreoffice.",
        ),
    ] = "auto",
) -> None:
    """Convert documents between formats using Pandoc or LibreOffice."""
    out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(
        f"[bold cyan]Converting [yellow]{input_file.name}[/yellow] to [green]{format.upper()}[/green] "
        f"(engine: [magenta]{engine}[/magenta])..."
    ):
        try:
            converter = get_document_converter()
            in_fmt = input_file.suffix.lstrip(".").lower()
            asyncio.run(
                converter.convert(
                    input_path=input_file,
                    output_path=out_path,
                    input_format=in_fmt,
                    output_format=format.lower(),
                    job_id="cli-direct",
                    preferred_engine=engine.lower(),
                )
            )
        except Exception as e:
            print_error(f"Failed to convert document: {e}")
            raise typer.Exit(code=1)

    in_size = input_file.stat().st_size
    out_size = out_path.stat().st_size

    print_success(
        f"Converted: [bold]{input_file.name}[/bold] ({format_file_size(in_size)}) ➔ "
        f"[bold]{out_path.name}[/bold] ({format_file_size(out_size)})\n"
        f"Saved to: [underline]{out_path}[/underline]",
        title="Document Converted",
    )
