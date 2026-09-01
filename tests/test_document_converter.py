"""Behavior tests for the document converter's PDF-to-Markdown path.

Verifies that a real PDF produces a real Markdown file (text + structure)
via pymupdf4llm, and that unsupported pdf targets still fail cleanly.
"""

import pymupdf
import pytest

from shared.exceptions import UnsupportedFormatError
from src.infrastructure.converters.document_converter import get_document_converter


def _make_pdf(path, text="Hello Markdown World") -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


@pytest.mark.asyncio
async def test_pdf_to_markdown_produces_text(tmp_path):
    inp = tmp_path / "in.pdf"
    _make_pdf(inp)
    out = tmp_path / "out"

    converter = get_document_converter()
    result = await converter.convert(inp, out, "pdf", "md", "testjob")

    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "Hello Markdown World" in content


@pytest.mark.asyncio
async def test_pdf_to_unsupported_target_raises(tmp_path):
    inp = tmp_path / "in.pdf"
    _make_pdf(inp)
    out = tmp_path / "out"

    converter = get_document_converter()
    with pytest.raises(UnsupportedFormatError):
        await converter.convert(inp, out, "pdf", "doc", "testjob")
