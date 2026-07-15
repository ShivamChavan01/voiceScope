from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import time
import os


RATE_LIMIT = int(os.getenv("RATE_LIMIT_RPM", "60"))
MAX_TRACKED_IPS = 10_000
CLEANUP_INTERVAL = 300


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        now = time.time()

        if now - self._last_cleanup > CLEANUP_INTERVAL:
            self._cleanup(now)
            self._last_cleanup = now

        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > now - 60]

        if len(self.requests[client_ip]) >= RATE_LIMIT:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded. Try again later."}
            )

        self.requests[client_ip].append(now)
        return await call_next(request)

    def _cleanup(self, now: float):
        window_start = now - 60
        stale = [k for k, v in self.requests.items() if not v or v[-1] < window_start]
        for k in stale:
            del self.requests[k]

        if len(self.requests) > MAX_TRACKED_IPS:
            sorted_keys = sorted(self.requests, key=lambda k: self.requests[k][-1] if self.requests[k] else 0)
            for k in sorted_keys[: len(self.requests) - MAX_TRACKED_IPS]:
                del self.requests[k]

    def _get_client_ip(self, request: Request) -> str:
        if request.client:
            return request.client.host
        return "unknown"
