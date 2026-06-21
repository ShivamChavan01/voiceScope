import os

os.environ["VALID_API_KEYS"] = "test-key"

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}

VALID_PAYLOAD = {
    "event": "call.ended",
    "call_id": "call-abc-123",
    "recording_url": "https://cdn.example.com/recordings/call-abc-123.mp3",
    "metadata": {"agent_id": "agent_001", "platform": "vapi"},
}

MOCK_PIPELINE_RESULT = {
    "run_id": "test-run-001",
    "analysis": {
        "intent": "cancel subscription",
        "sentiment_arc": "negative",
        "hallucination_detected": False,
        "hallucination_evidence": None,
        "outcome": "resolved",
        "escalation_signal": False,
    },
    "report": {
        "quality_score": 75,
        "executive_summary": "Test summary",
        "key_findings": ["finding1"],
        "recommendations": ["rec1"],
    },
}


def _mock_httpx_response(status_code=200, content=b"fake-audio-data", content_type="audio/mpeg"):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.content = content
    mock_resp.headers = {"content-type": content_type}
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_resp,
        )
    return mock_resp


def _mock_httpx_client(response=None):
    if response is None:
        response = _mock_httpx_response()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestWebhookValid:
    @patch("api.routes.validate_callback_url", return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_valid_webhook(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=VALID_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "test-run-001"
        assert data["analysis"]["intent"] == "cancel subscription"

    @patch("api.routes.validate_callback_url", return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_webhook_with_cost_tracking(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        result_with_cost = {
            **MOCK_PIPELINE_RESULT,
            "provider": {
                "name": "openai",
                "model": "gpt-4o",
                "cost_usd": 0.01,
                "input_tokens": 100,
                "output_tokens": 50,
            },
        }
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=result_with_cost)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=VALID_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200


class TestWebhookInvalidPayload:
    def test_missing_fields(self):
        response = client.post(
            "/api/v1/webhooks/call-completed",
            json={"event": "call.ended"},
            headers=HEADERS,
        )
        assert response.status_code == 422

    def test_empty_body(self):
        response = client.post(
            "/api/v1/webhooks/call-completed",
            json={},
            headers=HEADERS,
        )
        assert response.status_code == 422


class TestWebhookWrongEvent:
    def test_call_started_rejected(self):
        payload = {**VALID_PAYLOAD, "event": "call.started"}
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "call.ended" in response.json()["detail"]


class TestWebhookSSRF:
    def test_private_ip_rejected(self):
        payload = {
            **VALID_PAYLOAD,
            "recording_url": "https://169.254.169.254/latest/meta-data",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "private" in response.json()["detail"].lower()

    def test_localhost_rejected(self):
        payload = {
            **VALID_PAYLOAD,
            "recording_url": "https://localhost/secret",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400

    def test_http_rejected(self):
        payload = {
            **VALID_PAYLOAD,
            "recording_url": "http://cdn.example.com/recording.mp3",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "https" in response.json()["detail"].lower()


class TestWebhookDownloadFailure:
    @patch("api.routes.validate_callback_url", return_value=True)
    @patch("api.routes.httpx.AsyncClient")
    def test_download_404(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.return_value = _mock_httpx_client(_mock_httpx_response(status_code=404))

        response = client.post(
            "/api/v1/webhooks/call-completed", json=VALID_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 400
        assert "download" in response.json()["detail"].lower()

    @patch("api.routes.validate_callback_url", return_value=True)
    @patch("api.routes.httpx.AsyncClient")
    def test_non_audio_content_type(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.return_value = _mock_httpx_client(
            _mock_httpx_response(content_type="text/html")
        )

        response = client.post(
            "/api/v1/webhooks/call-completed", json=VALID_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 400
        assert "not audio" in response.json()["detail"].lower()


class TestWebhookNoAuth:
    def test_no_api_key_rejected(self):
        response = client.post("/api/v1/webhooks/call-completed", json=VALID_PAYLOAD)
        assert response.status_code == 401
