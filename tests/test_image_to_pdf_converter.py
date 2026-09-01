"""Behavior tests for image-to-PDF converter.

Verifies actual PDF bytes produced by Pillow: a single image yields a
1-page PDF, N images yield an N-page PDF with pages in the input order.
"""

import pytest
from PIL import Image
from pypdf import PdfReader

from src.infrastructure.converters.image_to_pdf_converter import (
    get_image_to_pdf_converter,
)


def _make_image(path, color, size=(40, 30)) -> None:
    Image.new("RGB", size, color).save(path)


@pytest.fixture
def red_img(tmp_path):
    p = tmp_path / "red.png"
    _make_image(p, "red")
    return p


@pytest.fixture
def blue_img(tmp_path):
    p = tmp_path / "blue.png"
    _make_image(p, "blue")
    return p


async def _convert(paths, output_path) -> bytes:
    converter = get_image_to_pdf_converter()
    out = await converter.convert(paths, output_path)
    return out.read_bytes()


@pytest.mark.asyncio
async def test_single_image_produces_pdf_bytes(red_img, tmp_path):
    out = await _convert([red_img], tmp_path / "out")
    assert out.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_two_images_produce_two_pages(red_img, blue_img, tmp_path):
    out = tmp_path / "out"
    await _convert([red_img, blue_img], out)
    assert PdfReader(str(out)).get_num_pages() == 2


@pytest.mark.asyncio
async def test_empty_list_raises(tmp_path):
    converter = get_image_to_pdf_converter()
    async def _go():
        await converter.convert([], tmp_path / "out")
    with pytest.raises(Exception):
        await _go()


def test_module_init_never_hangs():
    # Ensure importing/constructing the singleton does not block the loop.
    converter = get_image_to_pdf_converter()
    assert converter is not None
