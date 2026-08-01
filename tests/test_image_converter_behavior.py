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
