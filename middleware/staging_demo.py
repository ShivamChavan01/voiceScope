"""Explicitly reject live processing routes in synthetic-only staging."""

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.staging import demo_enabled


class StagingDemoMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        safe_posts = {
            '/api/v1/demo/staging', '/api/v1/demo/reliability', '/api/v1/policies/rules',
            '/api/v1/guardrails/check', '/api/v1/harness/validate',
        }
        compare_fixture = re.fullmatch(r'/api/v1/runs/demo-[A-Za-z0-9_-]+/stt-review', request.url.path)
        if (demo_enabled() and request.method == 'POST'
                and request.url.path not in safe_posts and not compare_fixture):
            return JSONResponse(
                status_code=503,
                content={'detail': 'Synthetic demo mode: live processing, webhooks and external actions are disabled. Use the labeled demo calls.'},
                headers={'Cache-Control': 'no-store'},
            )
        return await call_next(request)
