"""ASGI rate limiter middleware using Redis ZSET sliding window.

Pure ASGI (not BaseHTTPMiddleware) to avoid per-request task overhead.
Lua script does check+increment+prune in a single Redis round trip.
Fail-open: if Redis is unavailable, requests pass through.
"""

import logging
import math
import time
import uuid
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

RATE_LIMIT_LUA = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local uid = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, uid)
    redis.call('EXPIRE', key, math.ceil(window))
    return {1, limit - count - 1, math.ceil(now + window)}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return {0, 0, math.ceil(tonumber(oldest[2]) + window - now)}
"""

EXCLUDED_PATHS = frozenset({"/health", "/", "/docs", "/redoc", "/openapi.json"})


class RateLimitMiddleware:
    """ASGI middleware enforcing per-IP sliding window rate limiting."""

    def __init__(self, app: ASGIApp, settings: Any = None) -> None:
        self.app = app
        self.settings = settings
        self._lua_sha: str | None = None

    async def _get_client_ip(self, scope: Scope) -> str:
        """Extract client IP from X-Forwarded-For or scope client."""
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                # ponytail: first value only, trust the leftmost proxy-set IP
                return value.split(b",")[0].strip().decode()
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _classify_tier(self, path: str) -> tuple[str, int, int]:
        """Return (tier_name, limit, window_seconds) for a given path."""
        if self.settings and path.startswith("/api/v1/upload"):
            return (
                "uploads",
                self.settings.rate_limit_uploads_per_hour,
                3600,
            )
        limit = (
            self.settings.rate_limit_general_per_minute
            if self.settings
            else 60
        )
        window = (
            self.settings.rate_limit_window_seconds if self.settings else 60
        )
        return ("general", limit, window)

    async def _check_rate_limit(
        self, client_ip: str, tier: str, limit: int, window: int, redis: Any
    ) -> tuple[bool, int, int]:
        """Run the Lua script against Redis. Returns (allowed, remaining, reset_epoch)."""
        now = time.time()
        uid = f"{now}:{uuid.uuid4().hex}"
        key = f"ratelimit:{tier}:{client_ip}"

        try:
            # Cache the script SHA across calls
            if self._lua_sha is None:
                self._lua_sha = await redis.script_load(RATE_LIMIT_LUA)

            result = await redis.evalsha(
                self._lua_sha,
                1,
                key,
                str(window),
                str(limit),
                str(now),
                uid,
            )
            return bool(result[0]), int(result[1]), int(result[2])
        except Exception:
            # ponytail: reload SHA once after Redis restart, then propagate
            if self._lua_sha is not None:
                self._lua_sha = None
                self._lua_sha = await redis.script_load(RATE_LIMIT_LUA)
                result = await redis.evalsha(
                    self._lua_sha,
                    1,
                    key,
                    str(window),
                    str(limit),
                    str(now),
                    uid,
                )
                return bool(result[0]), int(result[1]), int(result[2])
            raise

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only rate-limit HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ponytail: skip OPTIONS — CORS preflights must pass through untouched
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Excluded paths pass through immediately
        if path in EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        # Feature toggle
        if self.settings and not self.settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        # Lazy import to avoid circular dependency at module load
        from src.lifespan import app_state

        # Fail open: no Redis → pass through
        if app_state.redis is None:
            logger.warning("Rate limiting unavailable, failing open")
            await self.app(scope, receive, send)
            return

        client_ip = await self._get_client_ip(scope)
        tier, limit, window = self._classify_tier(path)

        try:
            allowed, remaining, reset_epoch = await self._check_rate_limit(
                client_ip, tier, limit, window, app_state.redis
            )
        except Exception as exc:
            logger.warning(f"Rate limit check failed, failing open: {exc}")
            await self.app(scope, receive, send)
            return

        if not allowed:
            retry_after = max(1, reset_epoch - int(time.time()))
            body = b'{"error":"RateLimitError","message":"Rate limit exceeded"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"retry-after", str(retry_after).encode()],
                        [b"x-ratelimit-limit", str(limit).encode()],
                        [b"x-ratelimit-remaining", b"0"],
                        [b"x-ratelimit-reset", str(reset_epoch).encode()],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        # Wrap send to inject rate-limit headers into the first response chunk
        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(limit)
                headers["X-RateLimit-Remaining"] = str(remaining)
                headers["X-RateLimit-Reset"] = str(reset_epoch)
            await send(message)

        await self.app(scope, receive, send_with_headers)
