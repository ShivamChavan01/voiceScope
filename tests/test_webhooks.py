import json
import os
import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

import middleware.auth

middleware.auth._VALID_KEYS = frozenset(["test-key"])

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture(autouse=True)
def isolate_webhook_receipts(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))

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


class TestVapiWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_vapi_end_of_call_report(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

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
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_vapi_uses_mono_url(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        client.post("/api/v1/webhooks/call-completed", json=VAPI_PAYLOAD, headers=HEADERS)

        call_args = mock_httpx_cls.call_args
        assert "mono.mp3" in call_args[0][0]


class TestRetellWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_retell_call_ended(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        response = client.post(
            "/api/v1/webhooks/call-completed", json=RETELL_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "retell"
        assert data["call_id"] == "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6"

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_retell_uses_recording_url(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        client.post("/api/v1/webhooks/call-completed", json=RETELL_PAYLOAD, headers=HEADERS)

        call_args = mock_httpx_cls.call_args
        assert "retellai.s3" in call_args[0][0]


class TestGenericWebhook:
    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_generic_payload(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

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


class TestWebhookBodyLimits:
    def test_oversized_payload_rejected(self):
        # 413 before any processing — no body-size-based memory DoS
        payload = {"padding": "x" * (2 * 1024 * 1024 + 100)}
        response = client.post(
            "/api/v1/webhooks/call-completed",
            content=json.dumps(payload),
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert response.status_code == 413

    def test_malformed_json_rejected(self):
        response = client.post(
            "/api/v1/webhooks/call-completed",
            content=b"{not valid json",
            headers={**HEADERS, "Content-Type": "application/json"},
        )
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
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_download_404(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.side_effect = ValueError("Original recording could not be retrieved")

        response = client.post(
            "/api/v1/webhooks/call-completed", json=GENERIC_PAYLOAD, headers=HEADERS
        )
        assert response.status_code == 402
        assert "download" in response.json()["detail"].lower()

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_non_audio_content_type(self, mock_httpx_cls, mock_validate):
        mock_httpx_cls.side_effect = ValueError("Recording response is not audio")

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
    @pytest.mark.parametrize('body', [[], None, True, {'agent_id': 'agent', 'telephony_data': {}, 'status': 'completed', 'transcript': []}])
    def test_nonobject_and_invalid_execution_fields_are_rejected(self, body):
        response = client.post('/api/v1/webhooks/call-completed', content=json.dumps(body), headers={**HEADERS, 'Content-Type': 'application/json'})
        assert response.status_code == 400

    @pytest.mark.parametrize('source_id', [None, '', ' ', True, {}, 'None', '../other', 'call?token=private'])
    @patch('api.routes.get_pipeline')
    def test_invalid_bolna_id_cannot_claim_receipt_or_start_analysis(self, get_pipeline, source_id):
        response = client.post('/api/v1/webhooks/call-completed', json={**BOLNA_WEBHOOK, 'id': source_id}, headers=HEADERS)
        assert response.status_code == 400
        get_pipeline.assert_not_called()

    @pytest.mark.parametrize('number', ['NaN', 'Infinity', '-Infinity'])
    def test_nonfinite_json_is_rejected(self, number):
        response = client.post('/api/v1/webhooks/call-completed', content='{"metadata":'+number+'}', headers=HEADERS)
        assert response.status_code == 400

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
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_bland_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

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
    @patch('api.routes.get_pipeline')
    def test_completed_replay_reuses_saved_report_without_duplicate_provider_submission(self, get_pipeline, monkeypatch):
        import middleware.auth
        monkeypatch.setattr(middleware.auth, '_WEBHOOK_KEY', 'synthetic-bolna-webhook-secret')
        pipeline = AsyncMock()
        pipeline.run_from_transcript.return_value = {**MOCK_PIPELINE_RESULT, 'run_id': 'deduplicated-bolna-call'}
        get_pipeline.return_value = pipeline
        headers = {'X-Webhook-Key': 'synthetic-bolna-webhook-secret'}
        first = client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers=headers)
        assert first.status_code == 200
        second = client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers=headers)
        assert second.status_code == 200
        assert first.json()['run_id'] == second.json()['run_id']
        assert set(second.json()) == {'platform', 'call_id', 'run_id', 'status'}
        confused = client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers={**headers, 'X-API-Key': 'invalid'})
        assert confused.status_code == 200
        assert 'pipeline_result' not in confused.json()
        operator = client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers=HEADERS)
        assert operator.json()['pipeline_result']['stt_source']['segments']
        pipeline.run_from_transcript.assert_awaited_once_with(BOLNA_WEBHOOK['transcript'])
        assert client.get('/api/v1/runs', headers=headers).status_code == 401

    @patch('api.routes.get_pipeline')
    def test_failed_evaluation_can_be_retried(self, get_pipeline):
        pipeline = AsyncMock()
        pipeline.run_from_transcript.side_effect = [RuntimeError('synthetic outage'), {**MOCK_PIPELINE_RESULT, 'run_id': 'retry-bolna-call'}]
        get_pipeline.return_value = pipeline
        unsafe_client = TestClient(app, raise_server_exceptions=False)
        first = unsafe_client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers=HEADERS)
        assert first.status_code == 500
        second = client.post('/api/v1/webhooks/call-completed', json=BOLNA_WEBHOOK, headers=HEADERS)
        assert second.status_code == 200
        assert pipeline.run_from_transcript.await_count == 2

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_bolna_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        response = client.post(
            "/api/v1/webhooks/call-completed", json={**BOLNA_WEBHOOK, "transcript": None}, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "bolna"
        assert data["call_id"] == "7432382142914"

    @patch("api.routes.validate_callback_url_async", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.get_pipeline")
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    @patch("api.routes.BOLNA_API_KEY", "")
    def test_bolna_prefers_stable_endpoint_without_api_key(
        self, mock_httpx_cls, mock_get_pipeline, mock_validate
    ):
        # Regression: Bolna stopped serving raw S3 recording URLs (June 2026).
        # Even with no BOLNA_API_KEY, the stable api.bolna.ai endpoint MUST be
        # tried before the payload's recording_url — otherwise downloads fail
        # with 402 "Failed to download recording".
        import api.routes

        assert api.routes.BOLNA_API_KEY == ""  # no key configured in this env

        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        response = client.post(
            "/api/v1/webhooks/call-completed", json={**BOLNA_WEBHOOK, "transcript": None}, headers=HEADERS
        )
        assert response.status_code == 200
        assert mock_httpx_cls.await_count == 1
        requested = mock_httpx_cls.call_args_list[0].args[0]
        assert requested == "https://api.bolna.ai/recordings/call/7432382142914"
        assert "s3.amazonaws.com" not in requested


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
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_synthflow_with_recording(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

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
    @patch("api.routes.download_recording", new_callable=AsyncMock)
    def test_airai_completed(self, mock_httpx_cls, mock_get_pipeline, mock_validate):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=MOCK_PIPELINE_RESULT)
        mock_get_pipeline.return_value = mock_pipeline
        mock_httpx_cls.return_value = (b"fake-audio-data", "audio/mpeg")

        response = client.post(
            "/api/v1/webhooks/call-completed", json=AIRAI_WEBHOOK, headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "airai"
        assert data["call_id"] == "CAec7g2x30425ba039a83ffb4286754983"
