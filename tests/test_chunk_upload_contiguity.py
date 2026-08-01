"""Behavior tests: chunk uploads must not report completeness out of order.

Previously chunks_uploaded was derived as chunk_index + 1, so a client
uploading chunk 9 of 10 without chunks 0-8 reported 10/10 complete and
the job could start processing with missing chunks.
"""

from unittest.mock import AsyncMock

from src.application.commands import UploadChunkCommand
from src.application.handlers import UploadChunkHandler
from src.domain.job.job import Job
from src.domain.job.job_events import ChunkUploaded, JobCreated


def _created_job(total_chunks: int = 10) -> Job:
    job = Job("abc")
    job.apply_event(
        JobCreated.create(
            job_id="abc",
            file_id="f",
            input_format="txt",
            output_format="txt",
            file_size_bytes=1000,
            total_chunks=total_chunks,
        )
    )
    return job


def _chunk(index: int, total: int = 10) -> ChunkUploaded:
    return ChunkUploaded.create(
        job_id="abc",
        file_id="f",
        chunk_index=index,
        total_chunks=total,
        chunk_size_bytes=1,
    )


class FakeRepo:
    """Replays persisted events like the real repository does."""

    def __init__(self, created: JobCreated):
        self._events = [created]

    async def get_job(self, job_id: str) -> Job:
        job = Job(job_id)
        for event in self._events:
            job.apply_event(event)
        return job

    async def save_events(self, job_id: str, events) -> None:
        self._events.extend(events)


def test_aggregate_counts_unique_chunks():
    """chunks_uploaded must count unique indexes, not chunk_index + 1."""
    job = _created_job()

    # Upload chunk 9 first: 1 unique chunk, NOT 10/10 complete.
    job.apply_event(_chunk(9))
    assert job.chunks_uploaded == 1
    assert not job.all_chunks_uploaded()

    # Fill in 0..8: now all 10 unique chunks are present.
    for i in range(9):
        job.apply_event(_chunk(i))
    assert job.chunks_uploaded == 10
    assert job.all_chunks_uploaded()

    # Re-uploading an existing chunk must not double count.
    job.apply_event(_chunk(0))
    assert job.chunks_uploaded == 10


async def test_handler_out_of_order_chunks_never_report_complete():
    """is_complete must stay False until every index is present."""
    created = JobCreated.create(
        job_id="abc",
        file_id="f",
        input_format="txt",
        output_format="txt",
        file_size_bytes=1000,
        total_chunks=10,
    )
    repo = FakeRepo(created)
    storage = AsyncMock()
    handler = UploadChunkHandler(repo, storage)

    # Upload chunk 9, then chunk 5: only 2 unique chunks of 10.
    await handler.handle(UploadChunkCommand(job_id="abc", chunk_index=9, chunk_data=b"x"))
    result = await handler.handle(
        UploadChunkCommand(job_id="abc", chunk_index=5, chunk_data=b"y")
    )

    assert result["chunks_uploaded"] == 2
    assert result["is_complete"] is False

    # Upload the remaining indexes 0..8 (except 5) -> 10 unique chunks.
    for i in list(range(9)) + [7, 8]:
        await handler.handle(UploadChunkCommand(job_id="abc", chunk_index=i, chunk_data=b"z"))

    result = await handler.handle(
        UploadChunkCommand(job_id="abc", chunk_index=6, chunk_data=b"w")
    )
    assert result["chunks_uploaded"] == 10
    assert result["is_complete"] is True
