"""CLI commands for PDF operations (merge, split, rotate, encrypt, decrypt)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.pdf_processor import get_pdf_processor
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="pdf",
    help="PDF operations: merge, split, rotate, encrypt, and decrypt.",
    no_args_is_help=True,
)


@app.command("merge")
def merge_pdfs(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Two or more PDF files in the desired order.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Target merged PDF file path.",
        ),
    ],
) -> None:
    """Merge multiple PDF files into a single document."""
    if len(files) < 2:
        print_error("You must provide at least two PDF files to merge.")
        raise typer.Exit(code=1)

    for pdf in files:
        if not pdf.is_file():
            print_error(f"File not found: {pdf}")
            raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Merging {len(files)} PDFs..."):
        try:
            processor = get_pdf_processor()
            asyncio.run(
                processor.process(
                    input_path=files[0],
                    output_path=output,
                    operation="merge",
                    source_paths=files[1:],
                )
            )
        except Exception as e:
            print_error(f"Failed to merge PDFs: {e}")
            raise typer.Exit(code=1)

    out_size = output.stat().st_size
    print_success(
        f"Merged {len(files)} PDFs ({format_file_size(out_size)}).\nSaved to: [underline]{output}[/underline]",
        title="PDFs Merged",
    )


@app.command("split")
def split_pdf(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source PDF.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output path. For --pages, a PDF. For --start and --end, a ZIP containing parte.pdf and resto.pdf.",
        ),
    ],
    start_page: Annotated[
        int | None,
        typer.Option(
            "--start",
            "-s",
            min=1,
            help="Start page (1-based, inclusive). Must be used with --end.",
        ),
    ] = None,
    end_page: Annotated[
        int | None,
        typer.Option(
            "--end",
            "-e",
            min=1,
            help="End page (1-based, inclusive). Must be used with --start.",
        ),
    ] = None,
    pages: Annotated[
        str | None,
        typer.Option(
            "--pages",
            "-p",
            help="Comma-separated list of 1-based page numbers (e.g. '1,3,5').",
        ),
    ] = None,
) -> None:
    """Extract specific pages or page ranges from a PDF."""
    output.parent.mkdir(parents=True, exist_ok=True)
    processor = get_pdf_processor()

    with console.status(f"[bold cyan]Extracting pages from [yellow]{input_file.name}[/yellow]..."):
        try:
            if pages is not None:
                page_list = [int(p.strip()) for p in pages.split(",") if p.strip()]
                asyncio.run(
                    processor.process(
                        input_path=input_file,
                        output_path=output,
                        operation="extract_pages",
                        operation_params={"page_numbers": page_list},
                    )
                )
            elif start_page is not None and end_page is not None:
                asyncio.run(
                    processor.process(
                        input_path=input_file,
                        output_path=output,
                        operation="split_range",
                        operation_params={"start_page": start_page, "end_page": end_page},
                    )
                )
            else:
                print_error("Must specify either --pages or both --start and --end.")
                raise typer.Exit(code=1)
        except Exception as e:
            print_error(f"Failed to split PDF: {e}")
            raise typer.Exit(code=1)

    out_size = output.stat().st_size
    print_success(
        f"Pages extracted ({format_file_size(out_size)}).\nSaved to: [underline]{output}[/underline]",
        title="PDF Split",
    )


@app.command("rotate")
def rotate_pdf(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source PDF.",
        ),
    ],
    rotation: Annotated[
        int,
        typer.Option(
            "--rotation",
            "-r",
            help="Rotation in degrees (multiple of 90: 90, 180, 270).",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output PDF path. Defaults to [input_name]-rotated.pdf.",
        ),
    ] = None,
    pages: Annotated[
        str | None,
        typer.Option(
            "--pages",
            "-p",
            help="Optional comma-separated 1-based page numbers to rotate. If omitted, all pages are rotated.",
        ),
    ] = None,
) -> None:
    """Rotate pages in a PDF document."""
    if rotation % 90 != 0:
        print_error("Rotation angle must be a multiple of 90 degrees.")
        raise typer.Exit(code=1)

    out_path = resolve_output_path(input_file, output, "pdf") if output else input_file.parent / f"{input_file.stem}-rotated.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page_list = [int(p.strip()) for p in pages.split(",") if p.strip()] if pages else None

    with console.status(f"[bold cyan]Rotating pages by {rotation}°..."):
        try:
            processor = get_pdf_processor()
            params = {"rotation": rotation}
            if page_list:
                params["page_numbers"] = page_list
            asyncio.run(
                processor.process(
                    input_path=input_file,
                    output_path=out_path,
                    operation="rotate_pages",
                    operation_params=params,
                )
            )
        except Exception as e:
            print_error(f"Failed to rotate PDF: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Rotated PDF by {rotation}°.\nSaved to: [underline]{out_path}[/underline]",
        title="PDF Rotated",
    )


@app.command("encrypt")
def encrypt_pdf(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source PDF.",
        ),
    ],
    user_password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            help="Password required to open the PDF.",
        ),
    ],
    owner_password: Annotated[
        str | None,
        typer.Option(
            "--owner-password",
            help="Optional owner password with full permissions.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output PDF path. Defaults to [input_name]-encrypted.pdf.",
        ),
    ] = None,
) -> None:
    """Encrypt and protect a PDF file with a password."""
    out_path = resolve_output_path(input_file, output, "pdf") if output else input_file.parent / f"{input_file.stem}-encrypted.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status("[bold cyan]Encrypting PDF..."):
        try:
            processor = get_pdf_processor()
            params = {"user_password": user_password}
            if owner_password:
                params["owner_password"] = owner_password
            asyncio.run(
                processor.process(
                    input_path=input_file,
                    output_path=out_path,
                    operation="encrypt",
                    operation_params=params,
                )
            )
        except Exception as e:
            print_error(f"Failed to encrypt PDF: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Encrypted PDF successfully.\nSaved to: [underline]{out_path}[/underline]",
        title="PDF Encrypted",
    )


@app.command("decrypt")
def decrypt_pdf(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to encrypted PDF.",
        ),
    ],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            help="Password to unlock the PDF.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output PDF path. Defaults to [input_name]-decrypted.pdf.",
        ),
    ] = None,
) -> None:
    """Remove encryption and password protection from a PDF."""
    out_path = resolve_output_path(input_file, output, "pdf") if output else input_file.parent / f"{input_file.stem}-decrypted.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status("[bold cyan]Decrypting PDF..."):
        try:
            processor = get_pdf_processor()
            asyncio.run(
                processor.process(
                    input_path=input_file,
                    output_path=out_path,
                    operation="decrypt",
                    operation_params={"password": password},
                )
            )
        except Exception as e:
            print_error(f"Failed to decrypt PDF: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Decrypted PDF successfully.\nSaved to: [underline]{out_path}[/underline]",
        title="PDF Decrypted",
    )
