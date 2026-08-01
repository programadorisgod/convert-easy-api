"""WebSocket gateway for real-time job updates.

Provides WebSocket endpoint for clients to receive real-time
notifications about job progress and status changes.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from shared.config import get_settings
from shared.exceptions import JobNotFoundError
from src.infrastructure.events import get_connection_manager
from src.lifespan import get_repository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# WebSocket close codes (4000+ are application-defined).
WS_POLICY_VIOLATION = 1008
WS_JOB_NOT_FOUND = 4404


@router.websocket("/jobs/{job_id}")
async def job_updates(job_id: str, websocket: WebSocket):
    """WebSocket endpoint for job updates.

    Clients connect to this endpoint to receive real-time updates
    about their conversion job.

    Message format:
    {
        "event": "job:started",
        "jobId": "abc-123",
        "data": {...},
        "timestamp": "2026-03-11T10:30:00Z"
    }

    Events:
    - connection:established - Connection successful
    - job:created - Job created
    - job:chunk_uploaded - Chunk uploaded with progress
    - job:started - Processing started
    - job:completed - Conversion completed
    - job:failed - Conversion failed
    - job:cancelled - Job cancelled

    Args:
        job_id: Job identifier to subscribe to
        websocket: WebSocket connection
    """
    # Reject cross-site connections: browsers always send an Origin header,
    # so a page on an untrusted origin must never subscribe to job events.
    origin = websocket.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        logger.warning(f"WebSocket rejected for job {job_id}: bad origin {origin}")
        await websocket.close(code=WS_POLICY_VIOLATION)
        return

    # Reject unknown jobs: a job_id is the only capability token, so we must
    # not subscribe a client to a job that does not exist.
    try:
        await get_repository().get_job(job_id)
    except JobNotFoundError:
        logger.warning(f"WebSocket rejected: job {job_id} not found")
        await websocket.close(code=WS_JOB_NOT_FOUND)
        return

    manager = get_connection_manager()

    try:
        # Connect client
        await manager.connect(job_id, websocket)
        logger.info(f"WebSocket connected for job {job_id}")

        # Keep connection alive and listen for messages
        while True:
            # Wait for client messages (mostly for keep-alive)
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}", exc_info=True)
    finally:
        # Disconnect client
        await manager.disconnect(job_id, websocket)
