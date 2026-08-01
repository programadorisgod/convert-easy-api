"""Behavior tests: temporary files must not survive a failed operation.

If a conversion or storage step fails midway, any temp file it created
(parte.pdf/resto.pdf, *.tmp) must be removed. Otherwise orphan files
accumulate in the temp dir until the hourly cleanup sweep.
"""

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from starlette.requests import ClientDisconnect

from shared.exceptions import ChunkAssemblyError
from src.infrastructure.converters.pdf_processor import PdfProcessor
from src.infrastructure.storage.file_storage import FileStorage
from src.lifespan import get_repository, get_storage
from src.main import app


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


def test_download_cleans_up_when_stream_aborts(tmp_path):
    """An aborted download must still delete input+output files.

    Cleanup lives in the generator's finally: if the client disconnects
    mid-stream, Starlette closes the generator with GeneratorExit before
    the code after the loop would run, so the files would leak until the
    hourly sweep.
    """
    output_path = tmp_path / "abc_out"
    output_path.write_bytes(b"x" * 100)

    class FakeJob:
        status = SimpleNamespace(value="completed")
        output_format = "txt"
        file_id = "abc"

    storage = AsyncMock()
    storage.get_output = AsyncMock(return_value=output_path)
    storage.cleanup_file = AsyncMock()

    async def stream_then_abort():
        yield b"x" * 100
        raise ClientDisconnect("client aborted")

    storage.stream_file = stream_then_abort

    repo = AsyncMock()
    repo.get_job = AsyncMock(return_value=FakeJob())

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_repository] = lambda: repo

    try:
        with TestClient(app).stream("GET", "/api/v1/jobs/abc/download") as response:
            assert response.status_code == 200
            list(response.iter_raw())
    except Exception:
        # The disconnect error may surface on the client side too.
        pass
    finally:
        app.dependency_overrides.clear()

    storage.cleanup_file.assert_awaited_once_with("abc", include_output=True)
