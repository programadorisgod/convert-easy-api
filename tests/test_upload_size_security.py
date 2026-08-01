"""Behavior tests for upload size-limit enforcement.

Covers the three layers that close the "declare small, upload huge" bypass:
- MaxBodySizeMiddleware rejects oversized request bodies (memory DoS guard).
- Handlers reject chunks/files whose real bytes exceed the declared size.
- Schema caps total_chunks (assemble_chunks loops over that count).
"""

from pathlib import Path

import pytest

from shared.exceptions import ValidationError
from src.application.commands import UploadChunkCommand, UploadCompleteFileCommand
from src.application.handlers import UploadChunkHandler, UploadCompleteFileHandler
from src.domain.job import Job
from src.domain.job.job_status import JobStatus
from src.infrastructure.body_size_middleware import MaxBodySizeMiddleware
from src.interfaces.http.schemas.upload import CreateJobRequest


# ---------------------------------------------------------------------------
# MaxBodySizeMiddleware (ASGI level)
# ---------------------------------------------------------------------------

def _make_http_scope(content_length: bytes | None = None) -> dict:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", content_length))
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/upload/x/chunk",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 54321),
        "server": ("test", 80),
    }


class TestMaxBodySizeMiddleware:
    def test_content_length_over_limit_rejected(self):
        """A body announced as too large via Content-Length gets 413."""
        sent = []

        async def collect(message):
            sent.append(message)

        async def never_called_app(scope, receive, send):
            raise AssertionError("app must not be called for oversized body")

        mw = MaxBodySizeMiddleware(never_called_app, max_body_bytes=100)
        scope = _make_http_scope(content_length=b"200")

        import asyncio

        asyncio.run(mw(scope, None, collect))

        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 413
        assert b"exceeds size limit" in sent[1]["body"]

    def test_content_length_within_limit_passes(self):
        """A body within the limit is forwarded to the app."""
        called = []
        sent = []

        async def collect(message):
            sent.append(message)

        async def ok_app(scope, receive, send):
            called.append(True)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        mw = MaxBodySizeMiddleware(ok_app, max_body_bytes=100)
        scope = _make_http_scope(content_length=b"50")

        import asyncio

        asyncio.run(mw(scope, None, collect))

        assert called == [True]
        assert sent[0]["status"] == 200

    def test_streaming_body_over_limit_rejected(self):
        """Body streamed without Content-Length still gets truncated/413."""
        sent = []
        chunks = [b"a" * 80, b"b" * 80, b""]

        async def collect(message):
            sent.append(message)

        async def streaming_receive():
            return {
                "type": "http.request",
                "body": chunks.pop(0),
                "more_body": bool(chunks),
            }

        async def read_app(scope, receive, send):
            # App reads the whole body, then responds — like a controller
            total = 0
            while True:
                message = await receive()
                total += len(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"done"})

        mw = MaxBodySizeMiddleware(read_app, max_body_bytes=100)
        scope = _make_http_scope()  # no Content-Length

        import asyncio

        asyncio.run(mw(scope, streaming_receive, collect))

        # The middleware replaces the app's 200 with a 413 once the body
        # exceeded the limit — the app never buffers more than the limit.
        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 413

    def test_non_http_passthrough(self):
        """WebSocket scope is not touched."""
        mw = MaxBodySizeMiddleware(None, max_body_bytes=100)

        class NoopApp:
            async def __call__(self, scope, receive, send):
                self.called = True

        app = NoopApp()
        mw.app = app
        import asyncio

        asyncio.run(mw({"type": "websocket"}, None, None))
        assert app.called


# ---------------------------------------------------------------------------
# UploadChunkHandler — real bytes must not exceed declared size
# ---------------------------------------------------------------------------

class FakeRepository:
    def __init__(self, job):
        self.job = job

    async def get_job(self, job_id):
        return self.job

    async def save_events(self, job_id, events):
        pass


class FakeStorage:
    def __init__(self):
        self.saved = []

    async def save_chunk(self, file_id, chunk_index, chunk_data):
        self.saved.append((file_id, chunk_index, len(chunk_data)))
        return Path(f"/tmp/{file_id}_chunk_{chunk_index}")

    async def save_file(self, file_id, file_data):
        self.saved.append((file_id, 0, len(file_data)))
        return Path(f"/tmp/{file_id}")


def _make_job(file_size_bytes: int = 1024, total_chunks: int = 2) -> Job:
    job = Job("job-1")
    job.status = JobStatus.PENDING
    job.file_id = "file_id_placeholder"
    job.file_size_bytes = file_size_bytes
    job.total_chunks = total_chunks
    job.uploaded_bytes = 0
    return job


class TestUploadChunkSizeValidation:
    @pytest.mark.asyncio
    async def test_chunk_exceeding_declared_size_rejected(self):
        """Chunk bigger than the declared file size is rejected before save."""
        job = _make_job(file_size_bytes=1024)
        storage = FakeStorage()
        handler = UploadChunkHandler(FakeRepository(job), storage)

        with pytest.raises(ValidationError) as exc_info:
            await handler.handle(
                UploadChunkCommand(job_id="job-1", chunk_index=0, chunk_data=b"x" * 2048)
            )

        assert "exceed declared file size" in str(exc_info.value)
        assert storage.saved == []  # nothing written to disk

    @pytest.mark.asyncio
    async def test_cumulative_upload_exceeding_declared_size_rejected(self):
        """Sum of chunks exceeding declared size is rejected (disk-fill guard)."""
        job = _make_job(file_size_bytes=1024, total_chunks=2)
        job.uploaded_bytes = 768  # first chunk already uploaded
        storage = FakeStorage()
        handler = UploadChunkHandler(FakeRepository(job), storage)

        with pytest.raises(ValidationError):
            await handler.handle(
                UploadChunkCommand(job_id="job-1", chunk_index=1, chunk_data=b"y" * 512)
            )

        assert storage.saved == []

    @pytest.mark.asyncio
    async def test_chunk_within_declared_size_accepted(self):
        """A chunk that fits the declared size is saved normally."""
        job = _make_job(file_size_bytes=1024, total_chunks=2)
        storage = FakeStorage()
        handler = UploadChunkHandler(FakeRepository(job), storage)

        result = await handler.handle(
            UploadChunkCommand(job_id="job-1", chunk_index=0, chunk_data=b"z" * 512)
        )

        assert result["chunks_uploaded"] == 1
        assert storage.saved == [("file_id_placeholder", 0, 512)]


# ---------------------------------------------------------------------------
# UploadCompleteFileHandler — complete file must not exceed declared size
# ---------------------------------------------------------------------------

class TestUploadCompleteFileSizeValidation:
    @pytest.mark.asyncio
    async def test_file_exceeding_declared_size_rejected(self):
        """Complete file bigger than declared size is rejected before save."""
        job = _make_job(file_size_bytes=1024, total_chunks=1)
        storage = FakeStorage()
        handler = UploadCompleteFileHandler(FakeRepository(job), storage)

        with pytest.raises(ValidationError) as exc_info:
            await handler.handle(
                UploadCompleteFileCommand(job_id="job-1", file_data=b"x" * 4096)
            )

        assert "exceeds declared file size" in str(exc_info.value)
        assert storage.saved == []


# ---------------------------------------------------------------------------
# Schema — total_chunks is bounded
# ---------------------------------------------------------------------------

class TestTotalChunksCap:
    def test_total_chunks_over_cap_rejected(self):
        """Declaring more than 1000 chunks is a validation error (422)."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateJobRequest(
                input_format="png",
                output_formats=["jpg"],
                original_size=1024,
                total_chunks=1001,
            )

    def test_total_chunks_at_cap_accepted(self):
        req = CreateJobRequest(
            input_format="png",
            output_formats=["jpg"],
            original_size=1024,
            total_chunks=1000,
        )
        assert req.total_chunks == 1000


# ---------------------------------------------------------------------------
# Integration: middleware wired into the real app
# ---------------------------------------------------------------------------

class TestAppWiring:
    def test_app_rejects_oversized_content_length_with_413(self):
        """The app's middleware stack rejects oversized bodies (no Redis needed)."""
        import asyncio

        from src.main import app

        sent = []

        async def collect(message):
            sent.append(message)

        # 200MB > (100MB file + 1MB multipart slack) — fast-path rejection
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/convert/xml/html",
            "query_string": b"",
            "headers": [(b"content-length", str(200 * 1024 * 1024).encode())],
            "client": ("127.0.0.1", 54321),
            "server": ("test", 80),
        }

        async def no_body_receive():
            raise AssertionError("must not read body on fast-path reject")

        asyncio.run(app(scope, no_body_receive, collect))

        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 413
        assert b"exceeds size limit" in sent[1]["body"]
