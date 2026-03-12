"""WebSocket connection manager and event publisher.

Manages WebSocket connections and broadcasts domain events to connected clients.
Clients subscribe to specific job IDs and receive real-time updates.

Event format:
{
    "event": "job:started",
    "jobId": "abc123",
    "data": {...},
    "timestamp": "2026-03-11T10:30:00Z"
}
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from websockets.exceptions import ConnectionClosed

from shared.events import DomainEvent, get_event_bus
from src.domain.job import (
    JobCreated,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobCancelled,
    ChunkUploaded,
)


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and event broadcasting.

    Features:
    - Multiple clients can subscribe to the same job
    - Automatic cleanup of disconnected clients
    - Event filtering by job_id
    - Error isolation (one client error doesn't affect others)
    """

    def __init__(self):
        """Initialize connection manager."""
        # Map: job_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

        # Subscribe to all domain events
        event_bus = get_event_bus()
        event_bus.subscribe_all(self._handle_domain_event)

        logger.info("ConnectionManager initialized")

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection for a job.

        Args:
            job_id: Job identifier to subscribe to
            websocket: WebSocket connection
        """
        await websocket.accept()

        async with self._lock:
            self._connections[job_id].add(websocket)

        logger.info(
            f"Client connected to job {job_id} (total: {len(self._connections[job_id])})"
        )

        # Send connection confirmation
        await self._send_to_client(
            websocket,
            {
                "event": "connection:established",
                "jobId": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            job_id: Job identifier
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            self._connections[job_id].discard(websocket)

            # Clean up empty job entries
            if not self._connections[job_id]:
                del self._connections[job_id]

        logger.info(f"Client disconnected from job {job_id}")

    async def broadcast_to_job(self, job_id: str, message: dict[str, Any]) -> None:
        """Broadcast message to all clients subscribed to a job.

        Args:
            job_id: Job identifier
            message: Message to broadcast
        """
        async with self._lock:
            connections = self._connections.get(job_id, set()).copy()

        if not connections:
            return

        # Send to all clients, removing disconnected ones
        disconnected = []

        for websocket in connections:
            try:
                await self._send_to_client(websocket, message)
            except ConnectionClosed:
                logger.warning(f"Client connection closed for job {job_id}")
                disconnected.append(websocket)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections[job_id].discard(ws)

                if not self._connections[job_id]:
                    del self._connections[job_id]

    async def _send_to_client(
        self, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        """Send JSON message to a single client.

        Args:
            websocket: WebSocket connection
            message: Message to send
        """
        await websocket.send_json(message)

    async def _handle_domain_event(self, event: DomainEvent) -> None:
        """Handle domain events and broadcast to WebSocket clients.

        Translates domain events to WebSocket messages.

        Args:
            event: Domain event
        """
        try:
            message = self._event_to_message(event)

            if message:
                job_id = event.aggregate_id
                await self.broadcast_to_job(job_id, message)

        except Exception as e:
            logger.error(
                f"Failed to handle domain event {event.event_id}: {e}", exc_info=True
            )

    def _event_to_message(self, event: DomainEvent) -> dict[str, Any] | None:
        """Convert domain event to WebSocket message.

        Args:
            event: Domain event

        Returns:
            WebSocket message dict or None if event should not be broadcast
        """
        job_id = event.aggregate_id
        timestamp = event.timestamp.isoformat()

        # Map domain events to WebSocket event types
        if isinstance(event, JobCreated):
            return {
                "event": "job:created",
                "jobId": job_id,
                "data": {
                    "inputFormat": event.input_format,
                    "outputFormats": event.output_formats,
                    "originalSize": event.original_size,
                    "totalChunks": event.total_chunks,
                },
                "timestamp": timestamp,
            }

        elif isinstance(event, ChunkUploaded):
            return {
                "event": "job:chunk_uploaded",
                "jobId": job_id,
                "data": {
                    "chunkIndex": event.chunk_index,
                    "totalChunks": event.total_chunks,
                    "progress": round(
                        (event.chunk_index + 1) / event.total_chunks * 100, 2
                    ),
                },
                "timestamp": timestamp,
            }

        elif isinstance(event, JobStarted):
            return {
                "event": "job:started",
                "jobId": job_id,
                "data": {
                    "workerId": event.worker_id,
                },
                "timestamp": timestamp,
            }

        elif isinstance(event, JobCompleted):
            return {
                "event": "job:completed",
                "jobId": job_id,
                "data": {
                    "outputSize": event.output_size,
                    "processingTimeMs": event.processing_time_ms,
                },
                "timestamp": timestamp,
            }

        elif isinstance(event, JobFailed):
            return {
                "event": "job:failed",
                "jobId": job_id,
                "data": {
                    "errorMessage": event.error_message,
                    "errorCode": event.error_code,
                },
                "timestamp": timestamp,
            }

        elif isinstance(event, JobCancelled):
            return {
                "event": "job:cancelled",
                "jobId": job_id,
                "data": {
                    "reason": event.reason,
                },
                "timestamp": timestamp,
            }

        else:
            # Unknown event type - don't broadcast
            return None

    def get_connection_count(self, job_id: str | None = None) -> int:
        """Get number of active connections.

        Args:
            job_id: Optional job ID to filter by

        Returns:
            Number of active connections
        """
        if job_id:
            return len(self._connections.get(job_id, set()))
        else:
            return sum(len(conns) for conns in self._connections.values())

    def get_active_jobs(self) -> list[str]:
        """Get list of job IDs with active connections.

        Returns:
            List of job IDs
        """
        return list(self._connections.keys())


# Singleton instance
_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get connection manager singleton instance.

    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
