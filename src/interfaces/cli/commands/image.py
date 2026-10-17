"""CLI commands for image processing (convert, compress, remove-bg, watermark, to-pdf)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.image_compressor import CompressionLevel, get_image_compressor
from src.infrastructure.converters.image_converter import get_image_converter
from src.infrastructure.converters.image_pipeline import PipelineConfig, get_image_pipeline
from src.infrastructure.converters.image_to_pdf_converter import get_image_to_pdf_converter
from src.infrastructure.converters.watermark_service import WatermarkPosition, get_watermark_service
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="image",
    help="Image conversion, background removal, compression, watermarking and PDF generation.",
    no_args_is_help=True,
)


@app.command("convert")
def convert_image(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the source image file.",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Target image format (e.g., webp, png, jpg, avif, heic, gif, bmp, tiff).",
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
    quality: Annotated[
        int | None,
        typer.Option(
            "--quality",
            "-q",
            min=1,
            max=100,
            help="Output quality (1-100). If omitted, optimal default per format is used.",
        ),
    ] = None,
    strip_metadata: Annotated[
        bool,
        typer.Option(
            "--strip-metadata/--no-strip-metadata",
            help="Strip EXIF metadata for privacy.",
        ),
    ] = True,
) -> None:
    """Convert an image to another format using ImageMagick."""
    out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting [yellow]{input_file.name}[/yellow] to [green]{format.upper()}[/green]..."):
        try:
            converter = get_image_converter()
            asyncio.run(
                converter.convert(
                    input_path=input_file,
                    output_path=out_path,
                    output_format=format.lower(),
                    quality=quality,
                    strip_metadata=strip_metadata,
                )
            )
        except Exception as e:
            print_error(f"Failed to convert image: {e}")
            raise typer.Exit(code=1)

    in_size = input_file.stat().st_size
    out_size = out_path.stat().st_size
    print_success(
        f"Converted: [bold]{input_file.name}[/bold] ({format_file_size(in_size)}) ➔ "
        f"[bold]{out_path.name}[/bold] ({format_file_size(out_size)})\n"
        f"Saved to: [underline]{out_path}[/underline]",
        title="Image Converted",
    )


@app.command("remove-bg")
def remove_background(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the source image file.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. Defaults to [input_name]-nobg.png.",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Target format (png or webp recommended for transparency).",
        ),
    ] = "png",
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="AI model: u2net (general), u2netp (fast), u2net_human_seg (people), isnet-general-use, isnet-anime.",
        ),
    ] = "u2net",
    alpha_matting: Annotated[
        bool,
        typer.Option(
            "--alpha-matting/--no-alpha-matting",
            help="Enable alpha matting for smoother edges (slower).",
        ),
    ] = False,
    strip_metadata: Annotated[
        bool,
        typer.Option(
            "--strip-metadata/--no-strip-metadata",
            help="Strip EXIF metadata for privacy.",
        ),
    ] = True,
) -> None:
    """Remove background from image using AI (rembg)."""
    if output is None:
        out_path = input_file.parent / f"{input_file.stem}-nobg.{format.lstrip('.')}"
    else:
        out_path = resolve_output_path(input_file, output, format)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(
        remove_background=True,
        background_model=model,
        alpha_matting=alpha_matting,
        output_format=format.lower(),
        strip_metadata=strip_metadata,
        preserve_transparency=True,
    )

    with console.status(f"[bold cyan]Removing background with [yellow]{model}[/yellow] model..."):
        try:
            pipeline = get_image_pipeline()
            asyncio.run(
                pipeline.process(
                    input_path=input_file,
                    output_path=out_path,
                    config=config,
                )
            )
        except Exception as e:
            print_error(f"Failed to remove background: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Background removed successfully.\nSaved to: [underline]{out_path}[/underline]",
        title="Background Removed",
    )


@app.command("compress")
def compress_image(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the image to compress.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. Defaults to [input_name]-compressed.[ext].",
        ),
    ] = None,
    level: Annotated[
        str,
        typer.Option(
            "--level",
            "-l",
            help="Compression level: low (10-20%), balanced (30-60%), strong (60-90%).",
        ),
    ] = "balanced",
    quality: Annotated[
        int | None,
        typer.Option(
            "--quality",
            "-q",
            min=1,
            max=100,
            help="Manual quality override (1-100, lower = smaller file).",
        ),
    ] = None,
) -> None:
    """Compress JPEG, PNG, or WebP images using specialized optimizers."""
    ext = input_file.suffix.lstrip(".").lower()
    if output is None:
        out_path = input_file.parent / f"{input_file.stem}-compressed.{ext}"
    else:
        out_path = resolve_output_path(input_file, output, ext)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    level_map = {
        "low": CompressionLevel.LOW,
        "balanced": CompressionLevel.BALANCED,
        "strong": CompressionLevel.STRONG,
    }
    comp_level = level_map.get(level.lower(), CompressionLevel.BALANCED)

    with console.status(f"[bold cyan]Compressing [yellow]{input_file.name}[/yellow] ([green]{level}[/green])..."):
        try:
            compressor = get_image_compressor()
            asyncio.run(
                compressor.compress(
                    input_path=input_file,
                    output_path=out_path,
                    level=comp_level,
                    quality=quality,
                )
            )
        except Exception as e:
            print_error(f"Failed to compress image: {e}")
            raise typer.Exit(code=1)

    in_size = input_file.stat().st_size
    out_size = out_path.stat().st_size
    ratio = ((in_size - out_size) / in_size * 100) if in_size > 0 else 0

    print_success(
        f"Original: {format_file_size(in_size)} ➔ Compressed: {format_file_size(out_size)} "
        f"([bold green]{ratio:.1f}% reduction[/bold green])\n"
        f"Saved to: [underline]{out_path}[/underline]",
        title="Image Compressed",
    )


@app.command("watermark")
def watermark_image(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the image to watermark.",
        ),
    ],
    text: Annotated[
        str | None,
        typer.Option(
            "--text",
            "-t",
            help="Text for watermark.",
        ),
    ] = None,
    logo: Annotated[
        Path | None,
        typer.Option(
            "--logo",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to logo image file for watermark.",
        ),
    ] = None,
    position: Annotated[
        str,
        typer.Option(
            "--position",
            "-p",
            help="Position: center, top-left, top-right, bottom-left, bottom-right.",
        ),
    ] = "bottom-right",
    opacity: Annotated[
        float,
        typer.Option(
            "--opacity",
            min=0.0,
            max=1.0,
            help="Watermark opacity from 0.0 (transparent) to 1.0 (opaque).",
        ),
    ] = 0.7,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output path. Defaults to [input_name]-wm.[ext].",
        ),
    ] = None,
) -> None:
    """Add a text or logo watermark to an image."""
    if not text and not logo:
        print_error("Must specify either --text or --logo for watermarking.")
        raise typer.Exit(code=1)

    ext = input_file.suffix.lstrip(".").lower()
    if output is None:
        out_path = input_file.parent / f"{input_file.stem}-wm.{ext}"
    else:
        out_path = resolve_output_path(input_file, output, ext)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pos_map = {
        "center": WatermarkPosition.CENTER,
        "top-left": WatermarkPosition.TOP_LEFT,
        "top-right": WatermarkPosition.TOP_RIGHT,
        "bottom-left": WatermarkPosition.BOTTOM_LEFT,
        "bottom-right": WatermarkPosition.BOTTOM_RIGHT,
    }
    wm_pos = pos_map.get(position.lower(), WatermarkPosition.BOTTOM_RIGHT)

    with console.status("[bold cyan]Applying watermark..."):
        try:
            wm_service = get_watermark_service()
            if text:
                asyncio.run(
                    wm_service.add_text_watermark(
                        input_path=input_file,
                        output_path=out_path,
                        text=text,
                        position=wm_pos,
                        opacity=opacity,
                    )
                )
            elif logo:
                asyncio.run(
                    wm_service.add_logo_watermark(
                        input_path=input_file,
                        output_path=out_path,
                        logo_path=logo,
                        position=wm_pos,
                        opacity=opacity,
                    )
                )
        except Exception as e:
            print_error(f"Failed to apply watermark: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Watermark applied successfully.\nSaved to: [underline]{out_path}[/underline]",
        title="Watermark Applied",
    )


@app.command("to-pdf")
def images_to_pdf(
    images: Annotated[
        list[Path],
        typer.Argument(
            help="One or more image files in the desired page order.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Target output PDF file path.",
        ),
    ],
) -> None:
    """Combine one or more images into a single multi-page PDF."""
    if not images:
        print_error("You must provide at least one image file.")
        raise typer.Exit(code=1)

    for img in images:
        if not img.is_file():
            print_error(f"File not found: {img}")
            raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Combining {len(images)} image(s) into PDF..."):
        try:
            converter = get_image_to_pdf_converter()
            asyncio.run(
                converter.convert(
                    paths=images,
                    output_path=output,
                )
            )
        except Exception as e:
            print_error(f"Failed to create PDF from images: {e}")
            raise typer.Exit(code=1)

    out_size = output.stat().st_size
    print_success(
        f"Combined {len(images)} images into PDF ({format_file_size(out_size)}).\n"
        f"Saved to: [underline]{output}[/underline]",
        title="PDF Created",
    )
