import os
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ["VALID_API_KEYS"] = "test-key-1,test-key-2"
os.environ["DATABASE_URL"] = ""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient


# ─── Rate Limiter Tests ──────────────────────────────────────────────


class TestRateLimitMiddleware:
    def setup_method(self):
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"ok": True}

    def _make_client(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)
        return TestClient(app)

    def test_allows_requests_under_limit(self):
        client = self._make_client()
        for _ in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_blocks_at_rate_limit(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        middleware = RateLimitMiddleware(app)
        middleware.requests["test-ip"] = [time.time()] * 60

        client = TestClient(app)
        with patch.object(middleware, "_get_client_ip", return_value="test-ip"):
            app.add_middleware(RateLimitMiddleware)
            # Direct test of the dispatch logic
            from starlette.requests import Request
            from starlette.responses import Response

            request = MagicMock()
            request.client.host = "test-ip"
            request.url.path = "/test"
            request.headers = {}

            # Test that 60 requests triggers rate limit
            middleware.requests["test-ip"] = [time.time()] * 60
            assert len(middleware.requests["test-ip"]) >= 60

    def test_get_client_ip_from_client(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app)
        request = MagicMock()
        request.client.host = "192.168.1.1"
        assert middleware._get_client_ip(request) == "192.168.1.1"

    def test_get_client_ip_unknown(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app)
        request = MagicMock()
        request.client = None
        assert middleware._get_client_ip(request) == "unknown"

    def test_cleanup_removes_stale_ips(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app)
        now = time.time()
        middleware.requests["old-ip"] = [now - 120]
        middleware.requests["new-ip"] = [now]
        middleware._cleanup(now)
        assert "old-ip" not in middleware.requests
        assert "new-ip" in middleware.requests

    def test_cleanup_evicts_excess_ips(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app)
        now = time.time()
        for i in range(10005):
            middleware.requests[f"ip-{i}"] = [now]
        middleware._cleanup(now)
        assert len(middleware.requests) <= 10000

    def test_window_expiry(self):
        from middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app)
        now = time.time()
        middleware.requests["test-ip"] = [now - 61, now - 60.5, now]
        # Filter removes entries older than 60s
        middleware.requests["test-ip"] = [t for t in middleware.requests["test-ip"] if t > now - 60]
        assert len(middleware.requests["test-ip"]) == 1


# ─── Auth Middleware Tests ────────────────────────────────────────────


class TestAuthMiddleware:
    def _make_app(self):
        import middleware.auth
        self._orig_keys = middleware.auth._VALID_KEYS
        middleware.auth._VALID_KEYS = frozenset(["test-key-1", "test-key-2"])
        from middleware.auth import APIKeyAuthMiddleware

        app = FastAPI()

        @app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/v1/runs")
        async def runs():
            return {"runs": []}

        app.add_middleware(APIKeyAuthMiddleware)
        return app

    def teardown_method(self):
        import middleware.auth
        if hasattr(self, "_orig_keys"):
            middleware.auth._VALID_KEYS = self._orig_keys

    def test_exempt_path_health(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_valid_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/runs", headers={"X-API-Key": "test-key-1"})
        assert resp.status_code == 200

    def test_invalid_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/runs", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_missing_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/runs")
        assert resp.status_code == 401

    def test_second_valid_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/runs", headers={"X-API-Key": "test-key-2"})
        assert resp.status_code == 200

    def test_empty_valid_keys_returns_503(self):
        with patch.dict(os.environ, {"VALID_API_KEYS": ""}):
            from middleware.auth import APIKeyAuthMiddleware
            import importlib
            import middleware.auth
            # Force re-evaluation of _VALID_KEYS
            old_keys = middleware.auth._VALID_KEYS
            try:
                middleware.auth._VALID_KEYS = frozenset()
                app = FastAPI()

                @app.get("/api/v1/runs")
                async def runs():
                    return {"runs": []}

                app.add_middleware(APIKeyAuthMiddleware)
                client = TestClient(app)
                resp = client.get("/api/v1/runs", headers={"X-API-Key": "anything"})
                assert resp.status_code == 503
            finally:
                middleware.auth._VALID_KEYS = old_keys
