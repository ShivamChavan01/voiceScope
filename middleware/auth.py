from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os


EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/", "/api/v1/health"}


def _get_valid_keys() -> set[str]:
    return set(k.strip() for k in os.getenv("VALID_API_KEYS", "").split(",") if k.strip())


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        valid_keys = _get_valid_keys()
        if not valid_keys:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication not configured. Set VALID_API_KEYS environment variable."
                },
            )

        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key not in valid_keys:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)
