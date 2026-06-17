from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os


VALID_API_KEYS = set(
    k.strip() for k in os.getenv("VALID_API_KEYS", "").split(",") if k.strip()
)

EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/"}


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        if not VALID_API_KEYS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key not in VALID_API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)
