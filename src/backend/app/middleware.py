"""Production Hardening Middleware (Phase 8).

Includes:
1. SecurityHeadersMiddleware — Injects OWASP-compliant security headers.
2. StructuredLoggingMiddleware — Formats request/response logs as structured JSON.
3. RateLimiter — Sliding-window in-memory rate limiting with client IP tracking.
"""

import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException, status

logger = logging.getLogger("3d_cadastre.access")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds enterprise security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Emits structured JSON logs for observability and audit pipelines."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # Record metrics if metrics module is available
        from app.metrics import metrics_collector
        metrics_collector.increment_request(method, path)

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            metrics_collector.record_response(method, path, response.status_code, duration_ms)

            # Do not spam logs on frequent health/metrics probes during high-frequency polling
            if path not in ("/health", "/health/ready", "/metrics"):
                log_record = {
                    "timestamp": time.time(),
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
                logger.info(json.dumps(log_record))

            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_record = {
                "timestamp": time.time(),
                "request_id": request_id,
                "client_ip": client_ip,
                "method": method,
                "path": path,
                "status_code": 500,
                "error": str(exc),
                "duration_ms": duration_ms,
            }
            logger.error(json.dumps(log_record))
            metrics_collector.record_response(method, path, 500, duration_ms)
            raise exc


class RateLimiter:
    """Sliding-window in-memory rate limiter per IP address."""

    def __init__(self, requests_per_minute: int = 120):
        self.rpm = requests_per_minute
        self.window_seconds = 60
        self.history: Dict[str, List[float]] = defaultdict(list)

    def check(self, request: Request, custom_rpm: int = None) -> bool:
        client_ip = request.client.host if request.client else "127.0.0.1"
        limit = custom_rpm or self.rpm
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune older timestamps
        self.history[client_ip] = [ts for ts in self.history[client_ip] if ts > cutoff]

        if len(self.history[client_ip]) >= limit:
            return False

        self.history[client_ip].append(now)
        return True

    def __call__(self, request: Request):
        if not self.check(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please throttle requests.",
                headers={"Retry-After": "60"},
            )


# Default global rate limiter instances
global_rate_limiter = RateLimiter(requests_per_minute=300)
auth_rate_limiter = RateLimiter(requests_per_minute=30)
export_rate_limiter = RateLimiter(requests_per_minute=20)
