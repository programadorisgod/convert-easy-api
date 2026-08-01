"""Behavior tests: temporary files must not survive a failed operation.

If a conversion or storage step fails midway, any temp file it created
(parte.pdf/resto.pdf, *.tmp) must be removed. Otherwise orphan files
accumulate in the temp dir until the hourly cleanup sweep.
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfReader, PdfWriter

from shared.exceptions import ChunkAssemblyError
from src.infrastructure.converters.pdf_processor import PdfProcessor
from src.infrastructure.storage.file_storage import FileStorage


def _make_reader() -> PdfReader:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return PdfReader(buf)


def _make_storage(tmp_path: Path) -> FileStorage:
    storage = FileStorage()
    storage.temp_dir = tmp_path
    return storage


def test_split_range_removes_temp_pdfs_when_zip_fails(tmp_path):
    """If the zip step fails, parte.pdf/resto.pdf must not be left behind."""
    output_path = tmp_path / "split.zip"

    with patch("zipfile.ZipFile.write", side_effect=RuntimeError("zip boom")):
        with pytest.raises(RuntimeError):
            PdfProcessor()._split_range_to_zip(
                _make_reader(),
                output_path,
                {"start_page": 1, "end_page": 1},
            )

    assert not (tmp_path / "parte.pdf").exists()
    assert not (tmp_path / "resto.pdf").exists()


async def test_save_chunk_removes_temp_when_rename_fails(tmp_path):
    storage = _make_storage(tmp_path)
    chunk_path = storage._get_chunk_path("abc", 0)

    with patch("aiofiles.os.rename", side_effect=OSError("rename boom")):
        with pytest.raises(OSError):
            await storage.save_chunk("abc", 0, b"data")

    assert not chunk_path.with_suffix(".tmp").exists()
    assert not chunk_path.exists()


async def test_save_file_removes_temp_when_rename_fails(tmp_path):
    storage = _make_storage(tmp_path)
    file_path = storage._get_file_path("abc")

    with patch("aiofiles.os.rename", side_effect=OSError("rename boom")):
        with pytest.raises(OSError):
            await storage.save_file("abc", b"data")

    assert not file_path.with_suffix(".tmp").exists()
    assert not file_path.exists()


async def test_assemble_chunks_removes_temp_when_rename_fails(tmp_path):
    storage = _make_storage(tmp_path)
    for i in range(2):
        await storage.save_chunk("abc", i, b"chunk")

    output_path = storage._get_file_path("abc")

    with patch("aiofiles.os.rename", side_effect=OSError("rename boom")):
        with pytest.raises(ChunkAssemblyError):
            await storage.assemble_chunks("abc", 2)

    assert not output_path.with_suffix(".tmp").exists()
    assert not output_path.exists()
