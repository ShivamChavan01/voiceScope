import os
import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/", "/api/v1/health"}

# Cache at import time — env var doesn't change at runtime
_VALID_KEYS = frozenset(
    k.strip() for k in os.getenv("VALID_API_KEYS", "").split(",") if k.strip()
)
_WEBHOOK_KEY = os.getenv('BOLNA_WEBHOOK_SECRET', '')


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response

        webhook_key = request.headers.get('X-Webhook-Key', '')
        webhook_authorized = bool(
            request.method == 'POST' and request.url.path == '/api/v1/webhooks/call-completed' and _WEBHOOK_KEY
            and hmac.compare_digest(webhook_key.encode(), _WEBHOOK_KEY.encode())
        )
        if not _VALID_KEYS and not webhook_authorized:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication not configured. Set VALID_API_KEYS environment variable."
                },
                headers={'Cache-Control': 'no-store'},
            )

        api_key = request.headers.get("X-API-Key")
        operator_authorized = bool(api_key and any(hmac.compare_digest(api_key.encode(), key.encode()) for key in _VALID_KEYS))
        if not webhook_authorized and not operator_authorized:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"}, headers={'Cache-Control': 'no-store'})

        request.state.operator_authenticated = operator_authorized
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response
