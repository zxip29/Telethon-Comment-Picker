"""Simple in-memory rate limiting per client IP."""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            window_start = now - self.window_seconds
            self._hits[key] = [t for t in self._hits[key] if t > window_start]
            if len(self._hits[key]) >= self.max_requests:
                return False
            self._hits[key].append(now)
            return True

    def retry_after(self, key: str) -> int:
        with self._lock:
            if not self._hits[key]:
                return self.window_seconds
            oldest = min(self._hits[key])
            return max(1, int(self.window_seconds - (time.time() - oldest)))


_limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/comments":
            key = client_key(request)
            if not _limiter.is_allowed(key):
                retry = _limiter.retry_after(key)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": f"Too many requests. Try again in {retry} seconds.",
                        "total_fetched": 0,
                        "comments": [],
                    },
                    headers={"Retry-After": str(retry)},
                )
        return await call_next(request)
