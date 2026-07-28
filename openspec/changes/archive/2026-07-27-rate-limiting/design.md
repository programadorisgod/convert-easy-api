# Design: Rate Limiting

## Technical Approach

ASGI middleware using Redis sorted sets for sliding window rate limiting. One Redis round trip per request via a Lua script that atomically checks, increments, and prunes. Three tiers share the same middleware class; tier is selected by path prefix matching. Response headers injected by wrapping the ASGI `send` callable.

## Architecture Decisions

### Decision: Middleware type (ASGI vs Depends)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Pure ASGI middleware | Intercepts ALL requests including excluded paths; single check point; no route author cooperation needed | **Chosen** |
| FastAPI `Depends()` | Requires every route to opt-in; easy to forget; can't cover `/health`, `/docs` | Rejected |
| `BaseHTTPMiddleware` | Simpler API but adds a task per request; known性能 issues under load | Rejected |

**Rationale**: Pure ASGI is the only option that covers all routes without route-level opt-in. Zero overhead for excluded paths (path check before any Redis call).

### Decision: Redis data structure

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Sorted set (ZSET) | Atomic check+increment via Lua; O(log N) per op; self-pruning via ZREMRANGEBYSCORE | **Chosen** |
| Sliding window counter (two buckets) | Simpler but approximate; boundary burst issue | Rejected |
| Redis `INCR` + `EXPIRE` | Fixed window, not sliding; 2x burst at boundary | Rejected |

**Rationale**: ZSET gives true sliding window with atomic Lua. The sorted score IS the timestamp, so pruning is a single `ZREMRANGEBYSCORE`.

### Decision: Fail-open strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Fail open (allow request) | Availability > throttling; existing app_state.redis = None pattern already | **Chosen** |
| Fail closed (503) | Blocks all traffic on Redis outage; catastrophic for conversion API | Rejected |

**Rationale**: `app_state.redis` is already `None` when Redis is unavailable (lifespan.py:101-106). Middleware checks `app_state.redis is None` and passes through with warning log. Consistent with existing behavior.

## Data Flow

```
Request → RateLimitMiddleware.__call__
  ├─ scope["type"] != "http" → pass through (WebSocket, lifespan)
  ├─ path in EXCLUDED_PATHS → pass through
  ├─ app_state.redis is None → log warning, pass through (fail open)
  ├─ app.settings.rate_limit_enabled is False → pass through
  └─ Redis Lua script (ZSET check)
       ├─ allowed=True → wrap send() to inject headers → await self.app(...)
       └─ allowed=False → send 429 JSONResponse with Retry-After header
```

## Redis Operations

**Key pattern**: `ratelimit:{tier}:{client_ip}`
**Sorted set member**: `{timestamp_mono_ns}:{uuid4_hex}` (unique, monotonic)
**Score**: `time.time()` (float seconds)

**Lua script** (single round trip):
```lua
local key, window, limit, now, uid = KEYS[1], ARGV[1], ARGV[2], ARGV[3], ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, uid)
    redis.call('EXPIRE', key, math.ceil(window))
    return {1, limit - count - 1, math.ceil(now + window)}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return {0, 0, math.ceil(tonumber(oldest[2]) + window - now)}
```

Returns `[allowed, remaining, reset_epoch]`. `EXPIRE` on the key itself is the safety net for zombie keys (TTL = window ceiling).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/infrastructure/rate_limiter.py` | Create | ASGI middleware + Redis Lua script + tier classification |
| `shared/config/settings.py` | Modify | Add `rate_limit_enabled`, `rate_limit_general_per_minute` fields |
| `src/main.py` | Modify | Add `RateLimitMiddleware` after CORSMiddleware |

## Interfaces / Contracts

**Settings additions** (shared/config/settings.py):
```python
rate_limit_enabled: bool = True
rate_limit_general_per_minute: int = 60
# Existing: rate_limit_uploads_per_hour: int = 100
# Existing: rate_limit_concurrent_jobs_per_ip: int = 10
```

**Middleware signature** (src/infrastructure/rate_limiter.py):
```python
class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings | None = None): ...
    async def __call__(self, scope, receive, send): ...
```

**Tier classification** (path prefix → tier):
- `/api/v1/upload` → `uploads` (rate_limit_uploads_per_hour)
- Everything else → `general` (rate_limit_general_per_minute)
- Concurrent tier → already handled by BullMQ queue capacity, not this middleware

**Response headers** (all HTTP responses):
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1722067200
```

**Excluded paths**: `/health`, `/`, `/docs`, `/redoc`, `/openapi.json`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Tier classification, header injection, excluded path matching | Test middleware `__call__` with mock ASGI scope/receive/send |
| Unit | Lua script correctness | Test Redis ZSET operations directly against a test Redis |
| Integration | Full request flow with rate limit headers | httpx AsyncClient against test app with real Redis |
| Integration | Fail-open behavior | Mock `app_state.redis = None`, verify requests pass through |
| Integration | 429 response format | Hit limit, verify JSON body + Retry-After header |

## Migration / Rollout

No data migration. New settings have safe defaults (`rate_limit_enabled=True`, `rate_limit_general_per_minute=60`). Deploy and verify via `/health` (excluded) then observe `X-RateLimit-*` headers on API responses.

## Open Questions

- [ ] Should uploads tier also apply to `/api/v1/pdf/*` and `/api/v1/image/*` POST endpoints, or only `/api/v1/upload/*`? (Spec says uploads tier = upload paths only)
