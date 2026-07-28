# Rate Limiting Specification

## Purpose

ASGI middleware enforcing Redis sliding window rate limiting on all API endpoints. Protects against abuse with zero new dependencies. Three tiers: general, uploads, concurrent.

## Requirements

### Requirement: Sliding Window Rate Limiting

The system MUST enforce per-IP sliding window rate limiting via Redis sorted sets. Each request MUST atomically: expire old entries (`ZREMRANGEBYSCORE`), count current window (`ZCARD`), and record if under limit (`ZADD` + `EXPIRE`). Keys SHALL be `ratelimit:{ip}:{tier}:{window_start}`.

#### Scenario: Under limit — request allowed

- GIVEN a client with 40 requests in the current minute window
- WHEN a 41st request arrives
- THEN the request MUST pass through
- AND response MUST include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers

#### Scenario: At limit — request rejected

- GIVEN a client with 60 requests in the current minute (general tier)
- WHEN a 61st request arrives
- THEN the system MUST return HTTP 429
- AND the response body MUST be `{"error": "RateLimitError", "message": "Rate limit exceeded"}`
- AND the response MUST include `Retry-After` header with seconds until window reset

#### Scenario: Different IPs are independent

- GIVEN IP-A has 59 requests in the current window
- WHEN IP-B sends a request
- THEN IP-B MUST be rate-limited independently
- AND IP-B's window MUST NOT be affected by IP-A's usage

### Requirement: Rate Limit Tiers

The system MUST enforce three tiers with configurable limits:

| Tier | Default Limit | Window | Key Pattern |
|------|--------------|--------|-------------|
| General | 60 req/min | 60s | `ratelimit:{ip}:general:{ts}` |
| Uploads | 100 req/hr | 3600s | `ratelimit:{ip}:uploads:{ts}` |
| Concurrent | 10/IP | — | (handled by queue infra, not middleware) |

Upload tier SHALL apply to `POST /api/v1/upload` only. All other endpoints use general tier.

#### Scenario: Upload endpoint uses upload tier

- GIVEN a client with 99 uploads in the current hour
- WHEN the 100th upload request arrives
- THEN the request MUST pass (under limit)
- AND when the 101st arrives, HTTP 429 MUST be returned

#### Scenario: Non-upload endpoints use general tier

- GIVEN a client at the general limit (60/min)
- WHEN a request to `GET /api/v1/jobs/{id}` arrives
- THEN HTTP 429 MUST be returned regardless of upload tier usage

### Requirement: Response Headers

The system MUST include rate limit headers on ALL responses (not just 429):

| Header | Value |
|--------|-------|
| `X-RateLimit-Limit` | Max requests in current window |
| `X-RateLimit-Remaining` | Requests remaining in window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |

#### Scenario: Headers present on allowed response

- GIVEN a client with 30 requests remaining in the window
- WHEN any request is processed
- THEN response headers MUST include `X-RateLimit-Limit: 60`, `X-RateLimit-Remaining: 29`, `X-RateLimit-Reset: {unix_ts}`

#### Scenario: Headers present on 429 response

- GIVEN a client at the limit
- WHEN a request arrives
- THEN response MUST include all three headers
- AND `X-RateLimit-Remaining: 0`

### Requirement: IP Resolution

The system MUST resolve client IP from `X-Forwarded-For` header (first value) when present. MUST fall back to `request.client.host` when header is absent. MUST NOT trust spoofed headers when no reverse proxy is detected.

#### Scenario: X-Forwarded-For present

- GIVEN request has `X-Forwarded-For: 203.0.113.50, 70.41.3.18`
- WHEN rate limit is checked
- THEN the system MUST use `203.0.113.50` as the client IP

#### Scenario: No proxy header

- GIVEN request without `X-Forwarded-For`
- WHEN rate limit is checked
- THEN the system MUST use `request.client.host`

### Requirement: Path Exclusion

The system MUST NOT rate-limit the following paths: `/health`, `/`, `/docs`, `/redoc`, `/openapi.json`. All other paths under `settings.api_v1_prefix` SHALL be rate-limited.

#### Scenario: Health check bypasses limiter

- GIVEN a client at the rate limit
- WHEN `GET /health` is requested
- THEN the request MUST pass without rate limit check

#### Scenario: API endpoints are rate-limited

- GIVEN a client at the rate limit
- WHEN `GET /api/v1/jobs/{id}` is requested
- THEN HTTP 429 MUST be returned

### Requirement: Configuration

The system MUST support these settings: `rate_limit_enabled` (bool, default `True`), `rate_limit_general_per_minute` (int, default `60`), `rate_limit_uploads_per_hour` (int, default `100`, already exists), `rate_limit_window_seconds` (int, default `60`).

#### Scenario: Rate limiting disabled

- GIVEN `RATE_LIMIT_ENABLED=false`
- WHEN any request arrives
- THEN rate limit check MUST be skipped entirely

#### Scenario: Custom general limit

- GIVEN `RATE_LIMIT_GENERAL_PER_MINUTE=30`
- WHEN a client sends 30 requests in a minute
- THEN the 31st request MUST return HTTP 429

### Requirement: Redis Unavailability (Fail Open)

The system MUST fail open when Redis is unavailable. If the Redis pipeline fails, the system MUST log a warning and pass the request through WITHOUT rate limiting. The system MUST NOT return 503 for Redis errors.

#### Scenario: Redis connection lost

- GIVEN Redis is down
- WHEN a request arrives
- THEN the request MUST pass through
- AND a warning MUST be logged: "Rate limiting unavailable, failing open"

## Error Summary

| Error | HTTP | Body |
|-------|------|------|
| Rate limit exceeded | 429 | `{"error": "RateLimitError", "message": "Rate limit exceeded"}` |
