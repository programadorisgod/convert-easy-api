"""Behavior tests for image conversion output format.

The output file has no extension (UUID-based), so ImageMagick must be
told the target format explicitly. Verifies the actual bytes produced,
not internal calls.
"""

import pytest

from shared.config import get_settings
from src.infrastructure.converters.image_converter import get_image_converter


@pytest.fixture
def png_input(tmp_path) -> str:
    """Create a tiny real PNG via ImageMagick."""
    converter = get_image_converter()
    source = tmp_path / "in.png"
    cmd = [converter._magick_path, "-size", "10x10", "xc:red", str(source)]
    import asyncio

    async def _make():
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        assert proc.returncode == 0

    asyncio.run(_make())
    return str(source)


async def _convert_to(source: str, out_path, fmt: str) -> bytes:
    converter = get_image_converter()
    await converter.convert(
        input_path=__import__("pathlib").Path(source),
        output_path=__import__("pathlib").Path(out_path),
        output_format=fmt,
    )
    return __import__("pathlib").Path(out_path).read_bytes()


@pytest.mark.asyncio
async def test_png_to_webp_writes_webp_bytes(png_input, tmp_path):
    """Requesting webp must produce webp bytes, not the input format."""
    out = tmp_path / "out_noext"  # no extension, like production (UUID-based)
    data = await _convert_to(png_input, out, "webp")

    assert data[:4] == b"RIFF" and b"WEBP" in data[:12]


@pytest.mark.asyncio
async def test_png_to_jpeg_writes_jpeg_bytes(png_input, tmp_path):
    """Requesting jpeg must produce jpeg bytes, not the input format."""
    out = tmp_path / "out_noext"
    data = await _convert_to(png_input, out, "jpeg")

    assert data[:3] == b"\xff\xd8\xff"


@pytest.mark.asyncio
async def test_png_to_png_still_writes_png_bytes(png_input, tmp_path):
    """Same-format conversion still works."""
    out = tmp_path / "out_noext"
    data = await _convert_to(png_input, out, "png")

    assert data[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_png_to_avif_writes_avif_bytes(png_input, tmp_path):
    """Requesting avif must produce valid AVIF bytes via Pillow."""
    out = tmp_path / "out_noext"
    data = await _convert_to(png_input, out, "avif")

    # AVIF container has 'ftyp' at offset 4 and 'avif' / 'avis' / 'mif1' in the header
    assert b"ftyp" in data[:16]
    assert b"avif" in data[:32] or b"avis" in data[:32] or b"mif1" in data[:32]


@pytest.mark.asyncio
async def test_png_to_svg_writes_svg_bytes(png_input, tmp_path):
    """Requesting svg must produce valid SVG xml bytes via ImageMagick and potrace."""
    import shutil
    if not shutil.which("potrace"):
        pytest.skip("potrace not installed on host")

    out = tmp_path / "out_noext"
    data = await _convert_to(png_input, out, "svg")

    assert b"<svg" in data or b"<!DOCTYPE svg" in data


def test_sanitize_user_error_message():
    """Verify that internal paths and tool errors are never exposed in user messages."""
    from shared.exceptions import sanitize_user_error_message

    # Test ImageMagick delegate failure message from the user's issue
    leakage = (
        "magick: no encode delegate for this image format 'AVIF' @ warning/constitute.c/WriteImage/1403. "
        "magick: unable to open image 'AVIF:/tmp/easy_convert/eb133ed8-out': No such file @ error/blob.c/OpenBlob/3701."
    )
    sanitized = sanitize_user_error_message(leakage)
    assert "/tmp/" not in sanitized
    assert "constitute.c" not in sanitized
    assert "magick:" not in sanitized
    assert "error/blob.c" not in sanitized
    assert "currently not supported" in sanitized or "error occurred" in sanitized

    # Clean messages should be preserved
    clean = "Input file not found"
    assert sanitize_user_error_message(clean) == "Input file not found"
