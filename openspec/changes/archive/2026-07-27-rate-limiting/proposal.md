# Proposal: Rate Limiting

## Intent

Prevent abuse by adding Redis-based rate limiting using the existing `redis.asyncio` pool — zero new dependencies. Currently no request throttling exists on any endpoint.

## Scope

### In Scope
- ASGI middleware: Redis sliding window rate limiter (~60 LOC)
- 3 tiers: general (60/min), uploads (100/hr), concurrent jobs (10/IP)
- Settings: `rate_limit_general_per_minute`, `rate_limit_enabled`, `rate_limit_window_seconds`
- X-Forwarded-For IP detection for proxy deployments
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Excluded paths: `/health`, `/`, `/docs`, `/redoc`, `/openapi.json`
- Reuse existing `RateLimitError` + registered handler

### Out of Scope
- Per-user/auth rate limiting (no auth system yet)
- Distributed counters across instances
- Per-endpoint custom limits
- Concurrent job limiting at middleware level (handled by queue infra)

## Capabilities

### New Capabilities
- `rate-limiting`: Cross-cutting request throttling for all API endpoints

### Modified Capabilities
- None — additive change, existing spec behavior unchanged

## Approach

ASGI middleware using `redis.asyncio` pipeline for atomic sliding window:

```
key = f"ratelimit:{ip}:{bucket}"
```

Check: `ZREMRANGEBYSCORE` (expire old entries) → `ZCARD` (count). If under limit: `ZADD` timestamp → `EXPIRE` key TTL. If over: raise `RateLimitError(retry_after)`. Client IP via `X-Forwarded-For` header, fallback to `request.client.host`. Registered via `app.add_middleware()` in `main.py`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `shared/config/settings.py` | Modified | +3 rate limit settings |
| `src/infrastructure/rate_limiter.py` | New | Sliding window middleware |
| `src/main.py` | Modified | Register middleware |
| `.env.example` | Modified | Document new vars |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Redis latency adds to request time | Low | Single pipeline call, <1ms on same host |
| Misconfig locks out API | Low | `rate_limit_enabled` toggle; test before deploy |

## Rollback

Set `RATE_LIMIT_ENABLED=false` — middleware reads setting per-request, no restart needed. If import fails, comment out `app.add_middleware` line.

## Dependencies

Existing `redis>=5.0.0` (already in pyproject.toml). No new packages.

## Success Criteria

- [ ] 61st request/min from same IP returns 429 with `Retry-After`
- [ ] Different IPs are independently rate-limited
- [ ] `/health` and `/docs` bypass rate limiter
- [ ] `X-RateLimit-*` headers present on all throttled responses
- [ ] `X-Forwarded-For` IP respected when header is present
