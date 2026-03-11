"""WebSocket gateway for real-time job updates.

Provides WebSocket endpoint for clients to receive real-time
notifications about job progress and status changes.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.events import get_connection_manager


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


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
    manager = get_connection_manager()

    try:
        # Connect client
        await manager.connect(job_id, websocket)
        logger.info(f"WebSocket connected for job {job_id}")

        # Keep connection alive and listen for messages
        while True:
            # Wait for client messages (mostly for keep-alive)
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from client: {data}")
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}", exc_info=True)
    finally:
        # Disconnect client
        await manager.disconnect(job_id, websocket)
