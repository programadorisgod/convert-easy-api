"""Behavior tests: job status must not leak server filesystem paths.

Previously JobCompleted carried output_file_path (e.g. /tmp/easy_convert/abc_out)
and the status endpoint exposed it. The field was never consumed anywhere.
"""

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from src.domain.job.job import Job
from src.domain.job.job_events import JobCompleted, JobCreated
from src.lifespan import get_repository
from src.main import app


def _completed_job() -> Job:
    job = Job("abc")
    job.apply_event(
        JobCreated.create(
            job_id="abc",
            file_id="file-1",
            input_format="txt",
            output_format="pdf",
        )
    )
    job.apply_event(
        JobCompleted.create(
            job_id="abc",
            output_size_bytes=42,
            processing_time_seconds=1.5,
        )
    )
    return job


def test_job_status_does_not_expose_output_file_path():
    """GET /jobs/{id} must not include server paths in the response."""
    repo = AsyncMock()
    repo.get_job = AsyncMock(return_value=_completed_job())

    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = TestClient(app).get("/api/v1/jobs/abc")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "output_file_path" not in body
    assert body["status"] == "completed"


def test_job_to_dict_does_not_include_output_file_path():
    """The serialized aggregate must not carry the server path."""
    assert "output_file_path" not in _completed_job().to_dict()


def test_replay_ignores_legacy_output_file_path():
    """Old persisted events with output_file_path must still replay cleanly."""
    job = Job("abc")
    job.apply_event(
        JobCreated.create(
            job_id="abc",
            file_id="file-1",
            input_format="txt",
            output_format="pdf",
        )
    )
    legacy_event = JobCompleted.model_validate(
        {
            "event_type": "job.completed",
            "job_id": "abc",
            "aggregate_id": "abc",
            "output_file_path": "/tmp/easy_convert/abc_out",  # legacy field
            "output_size_bytes": 42,
            "processing_time_seconds": 1.5,
            "data": {
                "output_file_path": "/tmp/easy_convert/abc_out",
                "output_size_bytes": 42,
                "processing_time_seconds": 1.5,
            },
        }
    )
    job.apply_event(legacy_event)

    assert job.status.value == "completed"
    assert "output_file_path" not in job.to_dict()
