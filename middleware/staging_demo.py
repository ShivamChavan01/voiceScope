"""Explicitly reject live processing routes in synthetic-only staging."""

import re
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.staging import demo_enabled, public_demo_enabled, qa_agent_id, qa_deepgram_enabled


class StagingDemoMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        qa_enabled = bool(qa_agent_id())
        # Authentication middleware verifies the separate webhook credential first.
        # Public browsers only receive the operator proxy key, which is insufficient.
        qa_webhook = (qa_enabled and request.method == 'POST'
                      and request.url.path == '/api/v1/webhooks/call-completed'
                      and bool(os.getenv('BOLNA_WEBHOOK_SECRET'))
                      and hmac.compare_digest(request.headers.get('X-Webhook-Key', '').encode(),
                                              os.environ['BOLNA_WEBHOOK_SECRET'].encode()))
        qa_reference = (qa_deepgram_enabled() and request.method == 'POST'
                        and re.fullmatch(r'/api/v1/runs/[0-9a-fA-F-]{36}/stt-review/reference', request.url.path)
                        and bool(os.getenv('BOLNA_WEBHOOK_SECRET'))
                        and hmac.compare_digest(request.headers.get('X-Webhook-Key', '').encode(),
                                                os.environ['BOLNA_WEBHOOK_SECRET'].encode()))
        if public_demo_enabled():
            readable = request.url.path in {
                '/', '/health', '/api/v1/health', '/api/v1/runs',
                '/api/v1/runs/summary', '/api/v1/runs/history', '/api/v1/policies/rules',
                '/api/v1/loop/benchmark', '/api/v1/loop/benchmark/reliability',
                '/api/v1/costs', '/api/v1/harness/status',
            } or re.fullmatch(r'/api/v1/runs/demo-[A-Za-z0-9_-]+(?:/stt-review(?:/audio)?)?', request.url.path)
            if qa_enabled and re.fullmatch(r'/api/v1/runs/[0-9a-fA-F-]{36}(?:/stt-review(?:/audio)?)?', request.url.path):
                readable = True
            if not (qa_webhook or qa_reference) and (request.method not in ('GET', 'HEAD', 'OPTIONS') or not readable):
                return JSONResponse(
                    status_code=403,
                    content={'detail': 'Public synthetic demo is read-only. Uploads, configuration and live processing are disabled.'},
                    headers={'Cache-Control': 'no-store'},
                )
        safe_posts = {
            '/api/v1/demo/staging', '/api/v1/demo/reliability', '/api/v1/policies/rules',
            '/api/v1/guardrails/check', '/api/v1/harness/validate',
        }
        compare_fixture = re.fullmatch(r'/api/v1/runs/demo-[A-Za-z0-9_-]+/stt-review', request.url.path)
        if (demo_enabled() and request.method == 'POST'
                and request.url.path not in safe_posts and not compare_fixture and not qa_webhook and not qa_reference):
            return JSONResponse(
                status_code=503,
                content={'detail': 'Synthetic demo mode: live processing, webhooks and external actions are disabled. Use the labeled demo calls.'},
                headers={'Cache-Control': 'no-store'},
            )
        return await call_next(request)
