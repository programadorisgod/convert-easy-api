"""Request ID middleware for HTTP request correlation."""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.logging.context import set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates X-Request-ID and binds it to the logging context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Read incoming header or generate new UUID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:12]}"

        # Save to request state and contextvar
        request.state.request_id = request_id
        set_request_id(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            set_request_id("")
