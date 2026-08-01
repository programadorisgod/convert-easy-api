"""Tests for RateLimitMiddleware.

Unit tests mock Redis; integration tests require a live Redis.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import time

import pytest

from src.infrastructure.rate_limiter import (
    EXCLUDED_PATHS,
    RateLimitMiddleware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(
    path: str = "/api/v1/jobs",
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    if headers is None:
        headers = []
    return {
        "type": "http",
        "path": path,
        "method": method,
        "headers": headers,
        "client": ("127.0.0.1", 54321),
        "query_string": b"",
    }


def _make_settings(**overrides):
    """Build a minimal Settings-like mock."""
    s = MagicMock()
    s.rate_limit_enabled = overrides.get("rate_limit_enabled", True)
    s.rate_limit_general_per_minute = overrides.get(
        "rate_limit_general_per_minute", 60
    )
    s.rate_limit_window_seconds = overrides.get("rate_limit_window_seconds", 60)
    s.rate_limit_uploads_per_hour = overrides.get("rate_limit_uploads_per_hour", 100)
    s.rate_limit_trust_proxy = overrides.get("rate_limit_trust_proxy", False)
    return s


# ---------------------------------------------------------------------------
# Unit: _classify_tier
# ---------------------------------------------------------------------------

class TestClassifyTier:
    def test_upload_path_returns_uploads_tier(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        tier, limit, window = mw._classify_tier("/api/v1/upload")
        assert tier == "uploads"
        assert limit == 100
        assert window == 3600

    def test_upload_subpath_returns_uploads_tier(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        tier, _, _ = mw._classify_tier("/api/v1/upload/chunk/abc")
        assert tier == "uploads"

    def test_jobs_path_returns_general_tier(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        tier, limit, window = mw._classify_tier("/api/v1/jobs/123")
        assert tier == "general"
        assert limit == 60
        assert window == 60

    def test_health_excluded(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        tier, _, _ = mw._classify_tier("/health")
        # Excluded paths don't hit _classify_tier at all, but the function
        # still returns general by default — that's fine.
        assert tier == "general"


# ---------------------------------------------------------------------------
# Unit: _get_client_ip
# ---------------------------------------------------------------------------

class TestGetClientIp:
    @pytest.mark.asyncio
    async def test_xff_ignored_without_trusted_proxy(self):
        """Attacker-supplied X-Forwarded-For must not override the socket IP."""
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        scope = _make_scope(headers=[(b"x-forwarded-for", b"203.0.113.50")])
        ip = await mw._get_client_ip(scope)
        assert ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_spoofed_xff_chain_ignored_without_trusted_proxy(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        scope = _make_scope(
            headers=[(b"x-forwarded-for", b"203.0.113.50, 70.41.3.18")]
        )
        ip = await mw._get_client_ip(scope)
        assert ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_trusted_proxy_uses_rightmost_value(self):
        """With a trusted proxy, take the value the proxy appended (rightmost)."""
        mw = RateLimitMiddleware(
            MagicMock(), settings=_make_settings(rate_limit_trust_proxy=True)
        )
        scope = _make_scope(
            headers=[(b"x-forwarded-for", b"203.0.113.50, 70.41.3.18")]
        )
        ip = await mw._get_client_ip(scope)
        assert ip == "70.41.3.18"

    @pytest.mark.asyncio
    async def test_trusted_proxy_single_value(self):
        mw = RateLimitMiddleware(
            MagicMock(), settings=_make_settings(rate_limit_trust_proxy=True)
        )
        scope = _make_scope(headers=[(b"x-forwarded-for", b"203.0.113.50")])
        ip = await mw._get_client_ip(scope)
        assert ip == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_no_xff_falls_back_to_client(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        scope = _make_scope()
        ip = await mw._get_client_ip(scope)
        assert ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_no_client_returns_unknown(self):
        mw = RateLimitMiddleware(MagicMock(), settings=_make_settings())
        scope = _make_scope()
        scope["client"] = None
        ip = await mw._get_client_ip(scope)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_trusted_proxy_no_xff_falls_back_to_client(self):
        mw = RateLimitMiddleware(
            MagicMock(), settings=_make_settings(rate_limit_trust_proxy=True)
        )
        scope = _make_scope()
        ip = await mw._get_client_ip(scope)
        assert ip == "127.0.0.1"


# ---------------------------------------------------------------------------
# Unit: send_with_headers wrapper
# ---------------------------------------------------------------------------

class TestInjectHeaders:
    @pytest.mark.asyncio
    async def test_injects_rate_limit_headers(self):
        sent_messages = []

        async def fake_send(message):
            sent_messages.append(message)

        # Mock ASGI app that actually calls the send callback
        async def mock_asgi_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        settings = _make_settings()
        mw = RateLimitMiddleware(mock_asgi_app, settings=settings)

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha123")
        mock_redis.evalsha = AsyncMock(return_value=[1, 55, 9999999999])

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            await mw(scope, AsyncMock(), fake_send)

        assert sent_messages[0]["type"] == "http.response.start"
        headers_dict = dict(
            (k.decode(), v.decode()) for k, v in sent_messages[0]["headers"]
        )
        assert headers_dict["x-ratelimit-limit"] == "60"
        assert headers_dict["x-ratelimit-remaining"] == "55"


# ---------------------------------------------------------------------------
# Unit: Lua script execution
# ---------------------------------------------------------------------------

class TestLuaScriptExecution:
    @pytest.mark.asyncio
    async def test_sha_cached_after_first_call(self):
        settings = _make_settings()
        mw = RateLimitMiddleware(AsyncMock(), settings=settings)

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha_abc")
        mock_redis.evalsha = AsyncMock(return_value=[1, 59, 9999999999])

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        # script_load called once, evalsha called once
        mock_redis.script_load.assert_called_once()
        mock_redis.evalsha.assert_called_once()

        # Second request should reuse SHA
        mock_redis.reset_mock()
        sent.clear()
        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        mock_redis.script_load.assert_not_called()
        mock_redis.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_sha_reloaded_after_error(self):
        """If evalsha fails, SHA is cleared and retried once."""
        settings = _make_settings()
        mw = RateLimitMiddleware(AsyncMock(), settings=settings)
        mw._lua_sha = "stale_sha"

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fresh_sha")
        mock_redis.evalsha = AsyncMock(
            side_effect=[Exception("NOSCRIPT"), [1, 59, 9999999999]]
        )

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        # script_load re-called, evalsha called twice (fail + retry)
        mock_redis.script_load.assert_called_once()
        assert mock_redis.evalsha.call_count == 2


# ---------------------------------------------------------------------------
# Unit: 429 rejection
# ---------------------------------------------------------------------------

class TestRejectionResponse:
    @pytest.mark.asyncio
    async def test_returns_429_with_retry_after(self):
        settings = _make_settings()
        mw = RateLimitMiddleware(AsyncMock(), settings=settings)
        mw._lua_sha = "sha"

        # Use a future timestamp so retry-after = 60
        future_reset = int(time.time()) + 60
        mock_redis = AsyncMock()
        mock_redis.evalsha = AsyncMock(return_value=[0, 0, future_reset])

        sent = []

        async def fake_send(message):
            sent.append(message)

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            await mw(scope, AsyncMock(), fake_send)

        assert sent[0]["status"] == 429
        headers_dict = dict(
            (k.decode(), v.decode()) for k, v in sent[0]["headers"]
        )
        assert headers_dict["retry-after"] == "60"
        assert headers_dict["x-ratelimit-remaining"] == "0"


# ---------------------------------------------------------------------------
# Unit: fail-open
# ---------------------------------------------------------------------------

class TestFailOpen:
    @pytest.mark.asyncio
    async def test_no_redis_passes_through(self):
        settings = _make_settings()
        app = AsyncMock()
        mw = RateLimitMiddleware(app, settings=settings)

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = None
            scope = _make_scope()
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        # App should have been called (passthrough)
        app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_exception_passes_through(self):
        settings = _make_settings()
        app = AsyncMock()
        mw = RateLimitMiddleware(app, settings=settings)
        mw._lua_sha = "sha"

        mock_redis = AsyncMock()
        mock_redis.evalsha = AsyncMock(side_effect=Exception("connection lost"))

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = mock_redis
            scope = _make_scope()
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        # No 429 sent — request passed through
        assert sent == []
        app.assert_awaited_once()


# ---------------------------------------------------------------------------
# Unit: path exclusion
# ---------------------------------------------------------------------------

class TestPathExclusion:
    @pytest.mark.asyncio
    async def test_health_bypasses_rate_limit(self):
        settings = _make_settings()
        app = AsyncMock()
        mw = RateLimitMiddleware(app, settings=settings)

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = None  # Would fail-open anyway, but let's be explicit
            scope = _make_scope(path="/health")
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        # No rate limit response — just the passthrough
        assert sent == []
        app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_docs_bypasses_rate_limit(self):
        app = AsyncMock()
        mw = RateLimitMiddleware(app, settings=_make_settings())
        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = None
            scope = _make_scope(path="/docs")
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))
        assert sent == []
        app.assert_awaited_once()


# ---------------------------------------------------------------------------
# Unit: feature toggle
# ---------------------------------------------------------------------------

class TestFeatureToggle:
    @pytest.mark.asyncio
    async def test_disabled_bypasses_rate_limit(self):
        settings = _make_settings(rate_limit_enabled=False)
        app = AsyncMock()
        mw = RateLimitMiddleware(app, settings=settings)

        with patch("src.lifespan.app_state") as mock_state:
            mock_state.redis = None
            scope = _make_scope()
            sent = []
            await mw(scope, AsyncMock(), lambda m: sent.append(m))

        assert sent == []
        app.assert_awaited_once()


# ---------------------------------------------------------------------------
# Unit: non-HTTP passthrough
# ---------------------------------------------------------------------------

class TestNonHttpPassthrough:
    @pytest.mark.asyncio
    async def test_websocket_passes_through(self):
        mw = RateLimitMiddleware(AsyncMock(), settings=_make_settings())
        scope = {"type": "websocket"}
        sent = []
        await mw(scope, AsyncMock(), lambda m: sent.append(m))
        assert sent == []
