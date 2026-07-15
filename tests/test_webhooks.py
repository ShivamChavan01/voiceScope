import os

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

import middleware.auth
middleware.auth._VALID_KEYS = frozenset(["test-key"])

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}

VAPI_PAYLOAD = {
    "message": {
        "type": "end-of-call-report",
        "endedReason": "hangup",
        "call": {
            "id": "7420f27a-30fd-4f49-a995-5549ae7cc00d",
            "orgId": "eb166faa-7145-46ef-8044-589b47ae3b56",
            "type": "outboundPhoneCall",
            "status": "ended",
            "createdAt": "2024-09-10T11:14:12.339Z",
            "updatedAt": "2024-09-10T11:14:12.339Z",
            "startedAt": "2024-09-10T11:14:15.000Z",
            "endedAt": "2024-09-10T11:15:30.000Z",
            "cost": 0.05,
            "assistantId": "5b0a4a08-133c-4146-9315-0984f8c6be80",
            "recordingUrl": "https://storage.vapi.ai/7420f27a-recording.mp3",
        },
        "artifact": {
            "recording": {
                "monoUrl": "https://storage.vapi.ai/7420f27a-mono.mp3",
                "stereoUrl": "https://storage.vapi.ai/7420f27a-stereo.mp3",
            },
            "transcript": "AI: Thank you for calling. How can I help?\nUser: I need to cancel my subscription.",
            "messages": [
                {"role": "assistant", "message": "Thank you for calling. How can I help?"},
                {"role": "user", "message": "I need to cancel my subscription."},
            ],
        },
    }
}

RETELL_PAYLOAD = {
    "event": "call_ended",
    "call": {
        "call_type": "phone_call",
        "from_number": "+12137771234",
        "to_number": "+12137771235",
        "direction": "inbound",
        "call_id": "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6",
        "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
        "agent_name": "My Agent",
        "call_status": "ended",
        "start_timestamp": 1714608475945,
        "end_timestamp": 1714608491736,
        "duration_ms": 15791,
        "disconnection_reason": "user_hangup",
        "transcript": "Agent: Hi, how are you?\nUser: I need help with a refund.",
        "transcript_object": [
            {"role": "agent", "content": "Hi, how are you?"},
            {"role": "user", "content": "I need help with a refund."},
        ],
        "recording_url": "https://retellai.s3.us-west-2.amazonaws.com/recording.wav",
        "call_cost": {
            "product_costs": [
                {"product": "elevenlabs_tts", "unit_price": 1, "cost": 60},
                {"product": "openai_llm", "unit_price": 0.5, "cost": 30},
            ],
            "combined_cost": 90,
        },
    },
}

GENERIC_PAYLOAD = {
    "event": "call.ended",
    "call_id": "generic-call-001",
    "recording_url": "https://example.com/recordings/call-001.mp3",
    "transcript": "Agent: Hello. User: Hi, I have a question.",
    "metadata": {"source": "custom"},
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
    mock_client.head = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestVapiWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_vapi_end_of_call_report(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=VAPI_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "vapi"
        assert data["call_id"] == "7420f27a-30fd-4f49-a995-5549ae7cc00d"
        assert data["pipeline_result"]["run_id"] == "test-run-001"

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_vapi_uses_mono_url(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        client.post("/api/v1/webhooks/call-completed", json=VAPI_PAYLOAD, headers=HEADERS)

        call_args = mock_httpx_cls.return_value.get.call_args
        assert "mono.mp3" in call_args[0][0]


class TestRetellWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_retell_call_ended(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=RETELL_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "retell"
        assert data["call_id"] == "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6"

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_retell_uses_recording_url(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        client.post("/api/v1/webhooks/call-completed", json=RETELL_PAYLOAD, headers=HEADERS)

        call_args = mock_httpx_cls.return_value.get.call_args
        assert "retellai.s3" in call_args[0][0]


class TestGenericWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_generic_payload(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=GENERIC_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "generic"
        assert data["call_id"] == "generic-call-001"


class TestWebhookUnsupportedEvent:
    def test_call_started_rejected(self):
        payload = {**GENERIC_PAYLOAD, "event": "call.started"}
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"].lower()


class TestWebhookSSRF:
    def test_private_ip_rejected(self):
        payload = {
            "event": "call.ended",
            "call_id": "ssrf-test",
            "recording_url": "https://169.254.169.254/latest/meta-data",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "private" in response.json()["detail"].lower()

    def test_http_rejected(self):
        payload = {
            "event": "call.ended",
            "call_id": "ssrf-test",
            "recording_url": "http://example.com/recording.mp3",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "https" in response.json()["detail"].lower()

    def test_localhost_rejected(self):
        payload = {
            "event": "call.ended",
            "call_id": "ssrf-test",
            "recording_url": "https://localhost/secret.mp3",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400


class TestWebhookNoRecordingUrl:
    def test_vapi_no_recording(self):
        payload = {
            "message": {
                "type": "end-of-call-report",
                "endedReason": "hangup",
                "call": {"id": "no-rec-001", "status": "ended"},
                "artifact": {"transcript": "test"},
            }
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400
        assert "recording_url" in response.json()["detail"].lower()

    def test_retell_no_recording(self):
        payload = {
            "event": "call_ended",
            "call": {"call_id": "no-rec-002", "call_status": "ended"},
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 400


class TestWebhookDownloadFailure:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.httpx.AsyncClient")
    def test_download_404(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.return_value = _mock_httpx_client(_mock_httpx_response(status_code=404))

        response = client.post(
            "/api/v1/webhooks/call-completed", json=GENERIC_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 402
        assert "download" in response.json()["detail"].lower()

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.httpx.AsyncClient")
    def test_non_audio_content_type(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.return_value = _mock_httpx_client(
            _mock_httpx_response(content_type="text/html")
        )

        response = client.post(
            "/api/v1/webhooks/call-completed", json=GENERIC_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 400
        assert "not audio" in response.json()["detail"].lower()


class TestWebhookNoAuth:
    def test_no_api_key_rejected(self):
        response = client.post("/api/v1/webhooks/call-completed", json=GENERIC_PAYLOAD)
        assert response.status_code == 401


class TestWebhookInvalidPayload:
    def test_empty_body(self):
        response = client.post(
            "/api/v1/webhooks/call-completed",
            json={},
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert "recording_url" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bland.ai integration
# ---------------------------------------------------------------------------

BLAND_WEBHOOK = {
    "call_id": "12345678-1234-1234-1234-123456789012",
    "completed": True,
    "status": "completed",
    "concatenated_transcript": "user: Hello?\nassistant: Test call from Bland.",
    "corrected_duration": "11",
    "recording_url": "https://api.twilio.com/Recordings/RE456",
    "from": "+15559876543",
    "to": "+15551234567",
    "price": 0.017,
}


class TestBlandWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_bland_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=BLAND_WEBHOOK, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "bland"
        assert data["call_id"] == "12345678-1234-1234-1234-123456789012"


# ---------------------------------------------------------------------------
# Bolna integration
# ---------------------------------------------------------------------------

BOLNA_WEBHOOK = {
    "id": 7432382142914,
    "agent_id": "3c90c3cc-0d44-4b50-8888-8dd25736052a",
    "status": "completed",
    "conversation_duration": 123,
    "total_cost": 123,
    "transcript": "Agent: Hello! User: Check my order.",
    "telephony_data": {
        "recording_url": "https://bolna-recordings.s3.amazonaws.com/rec.mp3",
        "from_number": "+1987654007",
        "to_number": "+10123456789",
        "call_type": "outbound",
        "provider": "twilio",
    },
}


class TestBolnaWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_bolna_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=BOLNA_WEBHOOK, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "bolna"
        assert data["call_id"] == "7432382142914"


# ---------------------------------------------------------------------------
# Synthflow integration
# ---------------------------------------------------------------------------

SYNTHFLOW_WEBHOOK = {
    "call_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "agent_goodbye",
    "duration": 113,
    "transcript": "\nbot: Hey!\nhuman: Hi.",
    "collected_variables": {},
    "executed_actions": {},
}


class TestSynthflowWebhook:
    def test_synthflow_no_recording_rejected(self):
        response = client.post(
            "/api/v1/webhooks/call-completed", json=SYNTHFLOW_WEBHOOK, headers=HEADERS
        )
        assert response.status_code == 400
        assert "recording_url" in response.json()["detail"].lower()

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_synthflow_with_recording(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        payload = {
            **SYNTHFLOW_WEBHOOK,
            "recording_url": "https://synthflow.s3.amazonaws.com/rec.mp3",
        }
        response = client.post("/api/v1/webhooks/call-completed", json=payload, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "synthflow"
        assert data["call_id"] == "550e8400-e29b-41d4-a716-446655440000"


# ---------------------------------------------------------------------------
# Air.ai integration
# ---------------------------------------------------------------------------

AIRAI_WEBHOOK = {
    "call": {
        "sid": "CAec7g2x30425ba039a83ffb4286754983",
        "llmAnsweredBy": "human",
        "callRecordingUrl": "https://api.twilio.com/Recordings/RE25a9z",
        "fromNumber": "+17752432501",
        "toNumber": "+17752893647",
        "direction": "outbound-api",
        "duration": 44,
        "transcript": "BOT: Hey Tyler!\nHUMAN: How's it going?",
        "outcome": "Booked appointment",
    }
}


class TestAiraiWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.httpx.AsyncClient")
    def test_airai_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = _mock_httpx_client()

        response = client.post(
            "/api/v1/webhooks/call-completed", json=AIRAI_WEBHOOK, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "airai"
        assert data["call_id"] == "CAec7g2x30425ba039a83ffb4286754983"
