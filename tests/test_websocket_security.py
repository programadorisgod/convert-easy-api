"""Behavior tests: WebSocket must not subscribe to unknown or cross-site jobs.

The job_id is the only capability token, so the gateway must at least
refuse connections for jobs that do not exist and refuse browsers from
origins outside the CORS allow-list.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from unittest.mock import AsyncMock

from src.domain.job.job import Job
from src.main import app


def _fake_repo(job_exists: bool):
    repo = AsyncMock()

    async def fake_get_job(job_id):
        if not job_exists:
            from shared.exceptions import JobNotFoundError

            raise JobNotFoundError(job_id)
        return Job(job_id)

    repo.get_job = fake_get_job
    return repo


def test_ws_rejects_unknown_job(monkeypatch):
    """Connecting to a job that does not exist must be refused."""
    monkeypatch.setattr(
        "src.interfaces.http.controllers.websocket_controller.get_repository",
        lambda: _fake_repo(job_exists=False),
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/api/v1/ws/jobs/does-not-exist"):
            pass

    assert exc.value.code == 4404


def test_ws_rejects_cross_site_origin(monkeypatch):
    """A browser page from a disallowed origin must be refused."""
    monkeypatch.setattr(
        "src.interfaces.http.controllers.websocket_controller.get_repository",
        lambda: _fake_repo(job_exists=True),
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect(
            "/api/v1/ws/jobs/abc", headers={"origin": "https://evil.example"}
        ):
            pass

    assert exc.value.code == 1008


def test_ws_connects_for_existing_job(monkeypatch):
    """An existing job with no/trusted origin still connects."""
    monkeypatch.setattr(
        "src.interfaces.http.controllers.websocket_controller.get_repository",
        lambda: _fake_repo(job_exists=True),
    )

    with TestClient(app).websocket_connect("/api/v1/ws/jobs/abc") as ws:
        ws.send_text("ping")
