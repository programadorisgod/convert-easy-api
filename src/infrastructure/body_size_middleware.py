"""ASGI middleware that rejects request bodies larger than a byte limit.

Without this, endpoints call ``await file.read()`` / ``await chunk.read()``
and buffer the entire request body in memory regardless of the configured
``max_file_size_mb`` — a memory-exhaustion DoS vector.

Two guards:
- Content-Length header is checked first (fast path, clean 413).
- Streamed bodies are counted; once the limit is crossed, no further body
  bytes are forwarded to the app (it never buffers more than the limit) and
  the app's response is replaced with 413.
"""

import json
import logging

logger = logging.getLogger(__name__)


class MaxBodySizeMiddleware:
    """Reject requests whose body exceeds ``max_body_bytes``."""

    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: Content-Length is authoritative when present.
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    content_length = int(value)
                except ValueError:
                    break
                if content_length > self.max_body_bytes:
                    await self._reject(send)
                    return
                break

        received = 0
        too_large = False
        rejected = False
        responded = False

        async def receive_wrapper():
            nonlocal received, too_large
            if too_large:
                # Stop forwarding body; request is being rejected.
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    too_large = True
            return message

        async def send_wrapper(message):
            nonlocal rejected, responded
            if message["type"] in ("http.response.start", "http.response.body"):
                responded = True
            if rejected:
                # App is still emitting its response after our 413; drop it.
                return
            if too_large and message["type"] == "http.response.start":
                # The app read a truncated body and is about to respond;
                # replace its response with a clean 413.
                rejected = True
                await self._reject(send)
                return
            await send(message)

        await self.app(scope, receive_wrapper, send_wrapper)

        if too_large and not responded:
            # App finished without sending a response (e.g. it errored on the
            # truncated body). Send the 413 ourselves.
            await self._reject(send)

    async def _reject(self, send) -> None:
        """Send a 413 response with the API's error shape."""
        limit_mb = self.max_body_bytes / (1024 * 1024)
        body = json.dumps(
            {
                "error": "FileSizeLimitError",
                "message": f"Request body exceeds size limit of {limit_mb:.0f}MB",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
