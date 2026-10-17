"""Tool implementations for Easy Convert MCP server."""

import base64
import binascii
from pathlib import Path

from src.infrastructure.converters.audio_converter import get_audio_converter
from src.infrastructure.converters.document_converter import get_document_converter
from src.infrastructure.converters.image_converter import get_image_converter
from src.infrastructure.converters.image_pipeline import PipelineConfig, get_image_pipeline
from src.infrastructure.converters.image_to_pdf_converter import get_image_to_pdf_converter
from src.infrastructure.converters.pdf_processor import get_pdf_processor
from src.infrastructure.converters.video_converter import get_video_converter
from src.infrastructure.converters.xml_converter import XmlConverter
from src.interfaces.cli.ui import resolve_output_path
from src.interfaces.http.controllers.base64_controller import _extension_to_mime, _strip_data_uri


async def tool_convert_image(
    input_path: str,
    format: str,
    output_path: str | None = None,
    quality: int | None = None,
    strip_metadata: bool = True,
) -> str:
    """Convert an image to target format (webp, png, jpg, avif, heic, gif, bmp, tiff, svg, etc.)."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Input file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_image_converter()
    await converter.convert(
        input_path=in_file,
        output_path=out_file,
        output_format=format.lower(),
        quality=quality,
        strip_metadata=strip_metadata,
    )
    return f"Image converted successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_remove_image_background(
    input_path: str,
    output_path: str | None = None,
    format: str = "png",
    model: str = "u2net",
    alpha_matting: bool = False,
) -> str:
    """Remove background from image using AI (rembg)."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Input file not found: {input_path}"

    if output_path is None:
        out_file = in_file.parent / f"{in_file.stem}-nobg.{format.lstrip('.')}"
    else:
        out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve(), format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(
        remove_background=True,
        background_model=model,
        alpha_matting=alpha_matting,
        output_format=format.lower(),
        preserve_transparency=True,
    )
    pipeline = get_image_pipeline()
    await pipeline.process(
        input_path=in_file,
        output_path=out_file,
        config=config,
    )
    return f"Background removed successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_images_to_pdf(
    image_paths: list[str],
    output_path: str,
) -> str:
    """Combine one or more images into a single multi-page PDF document."""
    paths = [Path(p).expanduser().resolve() for p in image_paths]
    for p in paths:
        if not p.is_file():
            return f"Error: Image not found: {p}"

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_image_to_pdf_converter()
    await converter.convert(
        paths=paths,
        output_path=out_file,
    )
    return f"PDF created successfully from {len(paths)} images: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_convert_document(
    input_path: str,
    format: str,
    output_path: str | None = None,
    engine: str = "auto",
) -> str:
    """Convert documents between formats (PDF, DOCX, ODT, HTML, Markdown, EPUB, TXT, etc.) using Pandoc or LibreOffice."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Input document not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_document_converter()
    in_fmt = in_file.suffix.lstrip(".").lower()
    await converter.convert(
        input_path=in_file,
        output_path=out_file,
        input_format=in_fmt,
        output_format=format.lower(),
        job_id="mcp-direct",
        preferred_engine=engine.lower(),
    )
    return f"Document converted successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_pdf_merge(
    pdf_paths: list[str],
    output_path: str,
) -> str:
    """Merge two or more PDF files into a single PDF document in the specified order."""
    if len(pdf_paths) < 2:
        return "Error: At least two PDF files are required for merging."

    paths = [Path(p).expanduser().resolve() for p in pdf_paths]
    for p in paths:
        if not p.is_file():
            return f"Error: PDF file not found: {p}"

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    processor = get_pdf_processor()
    await processor.process(
        input_path=paths[0],
        output_path=out_file,
        operation="merge",
        source_paths=paths[1:],
    )
    return f"PDFs merged successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_pdf_split(
    input_path: str,
    output_path: str,
    pages: list[int] | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """Extract specific 1-based page numbers or a page range from a PDF."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: PDF file not found: {input_path}"

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    processor = get_pdf_processor()
    if pages:
        await processor.process(
            input_path=in_file,
            output_path=out_file,
            operation="extract_pages",
            operation_params={"page_numbers": pages},
        )
    elif start_page is not None and end_page is not None:
        await processor.process(
            input_path=in_file,
            output_path=out_file,
            operation="split_range",
            operation_params={"start_page": start_page, "end_page": end_page},
        )
    else:
        return "Error: Either 'pages' or both 'start_page' and 'end_page' must be specified."

    return f"PDF split successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_pdf_rotate(
    input_path: str,
    rotation: int,
    output_path: str | None = None,
    pages: list[int] | None = None,
) -> str:
    """Rotate PDF pages by a multiple of 90 degrees (90, 180, 270)."""
    if rotation % 90 != 0:
        return "Error: Rotation angle must be a multiple of 90 degrees."

    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: PDF file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, "pdf")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    params: dict = {"rotation": rotation}
    if pages:
        params["page_numbers"] = pages

    processor = get_pdf_processor()
    await processor.process(
        input_path=in_file,
        output_path=out_file,
        operation="rotate_pages",
        operation_params=params,
    )
    return f"PDF rotated successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_pdf_encrypt(
    input_path: str,
    password: str,
    output_path: str | None = None,
) -> str:
    """Encrypt and protect a PDF file with a password."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: PDF file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, "pdf")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    processor = get_pdf_processor()
    await processor.process(
        input_path=in_file,
        output_path=out_file,
        operation="encrypt",
        operation_params={"user_password": password},
    )
    return f"PDF encrypted successfully: {out_file}"


async def tool_pdf_decrypt(
    input_path: str,
    password: str,
    output_path: str | None = None,
) -> str:
    """Remove password protection from an encrypted PDF."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: PDF file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, "pdf")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    processor = get_pdf_processor()
    await processor.process(
        input_path=in_file,
        output_path=out_file,
        operation="decrypt",
        operation_params={"password": password},
    )
    return f"PDF decrypted successfully: {out_file}"


async def tool_convert_audio(
    input_path: str,
    format: str,
    output_path: str | None = None,
    bitrate: str | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    normalize: bool = False,
    trim_start: str | None = None,
    trim_duration: int | None = None,
) -> str:
    """Convert audio format (mp3, wav, flac, ogg, opus, aac, m4a, etc.) with normalization, channels and trimming."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Audio file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_audio_converter()
    await converter.convert(
        input_path=in_file,
        output_path=out_file,
        output_format=format.lower(),
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        normalize_volume=normalize,
        trim_start=trim_start,
        trim_duration=trim_duration,
    )
    return f"Audio converted successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_convert_video(
    input_path: str,
    format: str,
    output_path: str | None = None,
    crf: int | None = None,
    resolution: str | None = None,
    fps: int | None = None,
    mute: bool = False,
    trim_start: str | None = None,
    trim_duration: int | None = None,
) -> str:
    """Convert video format (mp4, webm, mkv, mov, avi, flv, gif, etc.) with resolution, FPS, CRF quality and mute."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Video file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_video_converter()
    await converter.convert(
        input_path=in_file,
        output_path=out_file,
        output_format=format.lower(),
        crf=crf,
        resolution=resolution,
        fps=fps,
        trim_start=trim_start,
        trim_duration=trim_duration,
        remove_audio=mute,
    )
    return f"Video converted successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_video_extract_audio(
    input_path: str,
    format: str = "mp3",
    output_path: str | None = None,
    bitrate: str = "192k",
) -> str:
    """Extract audio track from video file (mp3, wav, aac, flac, ogg, opus, m4a)."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Video file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    converter = get_video_converter()
    await converter.convert(
        input_path=in_file,
        output_path=out_file,
        output_format=format.lower(),
        extract_audio=True,
        audio_output_format=format.lower(),
        audio_bitrate=bitrate,
    )
    return f"Audio extracted from video successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_convert_xml(
    input_path: str,
    format: str = "json",
    output_path: str | None = None,
    preserve_attributes: bool = False,
    always_as_list: bool = False,
    xslt_path: str | None = None,
) -> str:
    """Convert XML file to JSON, YAML, or HTML (with optional XSLT)."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: XML file not found: {input_path}"

    out_file = resolve_output_path(in_file, Path(output_path).expanduser().resolve() if output_path else None, format)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    content = in_file.read_bytes()
    XmlConverter.validate_xml(content, in_file.name)

    options: dict = {
        "preserve_attributes": preserve_attributes,
        "always_as_list": always_as_list,
    }
    if xslt_path:
        xslt_file = Path(xslt_path).expanduser().resolve()
        if not xslt_file.is_file():
            return f"Error: XSLT file not found: {xslt_path}"
        options["xslt_content"] = xslt_file.read_bytes()
        res = await XmlConverter.convert(content, "xslt", options)
    else:
        res = await XmlConverter.convert(content, format.lower(), options)

    out_file.write_bytes(res.content)
    return f"XML converted to {format.upper()} successfully: {out_file} ({out_file.stat().st_size} bytes)"


async def tool_base64_encode_image(
    input_path: str,
    output_path: str | None = None,
    data_uri: bool = True,
) -> str:
    """Encode an image file into Base64 or Data URI format."""
    in_file = Path(input_path).expanduser().resolve()
    if not in_file.is_file():
        return f"Error: Image file not found: {input_path}"

    raw_bytes = in_file.read_bytes()
    mime = _extension_to_mime(in_file.name)
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    result = f"data:{mime};base64,{b64_str}" if data_uri else b64_str

    if output_path:
        out_file = Path(output_path).expanduser().resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(result, encoding="utf-8")
        return f"Base64 saved to {out_file} ({len(result)} chars)"
    return result


async def tool_base64_decode_image(
    input_data: str,
    output_path: str,
) -> str:
    """Decode a Base64 string or Data URI back into an image file."""
    try:
        possible_file = Path(input_data).expanduser().resolve()
        if possible_file.is_file():
            content = possible_file.read_text(encoding="utf-8")
        else:
            content = input_data

        clean_b64, _ = _strip_data_uri(content)
        raw_bytes = base64.b64decode(clean_b64, validate=True)

        out_file = Path(output_path).expanduser().resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(raw_bytes)
        return f"Image decoded successfully: {out_file} ({len(raw_bytes)} bytes)"
    except (binascii.Error, ValueError) as e:
        return f"Error: Invalid base64 payload: {e}"
