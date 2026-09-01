"""Behavior tests for ProcessImageToPdfHandler.

Uses in-memory fakes for the repository, queue and storage, and patches the
MIME validator so tests do not depend on libmagic. Verifies ordering of the
resolved source_file_ids and rejection of non-image sources.
"""

from pathlib import Path

import pytest

import src.application.handlers as handlers_module
from src.application.commands import ProcessImageToPdfCommand
from src.application.handlers import ProcessImageToPdfHandler
from src.domain.job import Job, JobCreated
from shared.exceptions import ValidationError


def _job(job_id: str, file_id: str, input_format: str) -> Job:
    job = Job(job_id)
    job.apply_event(
        JobCreated.create(
            job_id=job_id,
            file_id=file_id,
            input_format=input_format,
            output_format="png",
        )
    )
    return job


class FakeRepository:
    def __init__(self, jobs: dict[str, Job]):
        self.jobs = jobs
        self.saved: list = []

    async def get_job(self, job_id: str) -> Job:
        return self.jobs[job_id]

    async def save_events(self, job_id: str, events) -> None:
        self.saved.extend(events)


class FakeQueue:
    def __init__(self):
        self.enqueued: list[dict] = []

    async def enqueue(self, job_id: str, job_data: dict) -> None:
        self.enqueued.append({"job_id": job_id, "data": job_data})


class FakeStorage:
    def __init__(self, files: dict[str, Path]):
        self.files = files

    async def get_file(self, file_id: str) -> Path:
        return self.files[file_id]


@pytest.fixture
def png_file(tmp_path):
    p = tmp_path / "img.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    return p


@pytest.fixture
def handler(png_file, monkeypatch):
    primary = _job("j1", "f1", "png")
    source2 = _job("j2", "f2", "png")
    source3 = _job("j3", "f3", "png")
    non_image = _job("j4", "f4", "pdf")

    repo = FakeRepository(
        {
            "j1": primary,
            "j2": source2,
            "j3": source3,
            "j4": non_image,
        }
    )
    storage = FakeStorage(
        {
            "f1": png_file,
            "f2": png_file,
            "f3": png_file,
            "f4": png_file,
        }
    )
    queue = FakeQueue()

    # Bypass libmagic-dependent validation.
    monkeypatch.setattr(
        handlers_module, "get_mime_validator", lambda: type("V", (), {"validate": lambda self, p, f: "image/png"})()
    )

    return ProcessImageToPdfHandler(repo, queue, storage), repo, queue, storage


@pytest.mark.asyncio
async def test_enqueues_sources_in_order(handler):
    h, repo, queue, _ = handler
    result = await h.handle(ProcessImageToPdfCommand(job_id="j1", source_job_ids=["j2", "j3"]))

    assert result["status"] == "queued"
    assert result["page_count"] == 3

    payload = queue.enqueued[0]["data"]
    assert payload["output_format"] == "pdf"
    assert payload["image_to_pdf_config"]["source_file_ids"] == ["f2", "f3"]

    assert len(repo.saved) == 1
    assert repo.saved[0].event_type == "job.images_to_pdf_configured"


@pytest.mark.asyncio
async def test_rejects_non_image_source(handler):
    h, _, _, _ = handler
    with pytest.raises(ValidationError):
        await h.handle(
            ProcessImageToPdfCommand(job_id="j1", source_job_ids=["j4"])
        )
