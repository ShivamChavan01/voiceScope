from api.schemas import (
    detect_and_parse_webhook,
    parse_vapi_webhook,
    parse_retell_webhook,
    parse_bland_webhook,
    parse_bolna_webhook,
    parse_synthflow_webhook,
    parse_airai_webhook,
    parse_generic_webhook,
)


# ---------------------------------------------------------------------------
# Vapi
# ---------------------------------------------------------------------------

VAPI_PAYLOAD = {
    "message": {
        "type": "end-of-call-report",
        "endedReason": "hangup",
        "call": {
            "id": "7420f27a-30fd-4f49-a995-5549ae7cc00d",
            "orgId": "eb166faa-7145-46ef-8044-589b47ae3b56",
            "status": "ended",
            "startedAt": "2024-09-10T11:14:15.000Z",
            "endedAt": "2024-09-10T11:15:30.000Z",
            "cost": 0.05,
            "assistantId": "5b0a4a08-133c-4146-9315-0984f8c6be80",
            "recordingUrl": "https://storage.vapi.ai/recording.mp3",
        },
        "artifact": {
            "recording": {
                "monoUrl": "https://storage.vapi.ai/mono.mp3",
                "stereoUrl": "https://storage.vapi.ai/stereo.mp3",
            },
            "transcript": "AI: How can I help? User: I need a refund.",
            "messages": [
                {"role": "assistant", "message": "How can I help?"},
                {"role": "user", "message": "I need a refund."},
            ],
        },
    }
}


class TestVapiParser:
    def test_detects_vapi(self):
        event = detect_and_parse_webhook(VAPI_PAYLOAD)
        assert event.platform == "vapi"

    def test_parses_correctly(self):
        event = parse_vapi_webhook(VAPI_PAYLOAD)
        assert event.call_id == "7420f27a-30fd-4f49-a995-5549ae7cc00d"
        assert event.recording_url == "https://storage.vapi.ai/mono.mp3"
        assert event.transcript == "AI: How can I help? User: I need a refund."
        assert event.duration_ms == 75000
        assert event.ended_reason == "hangup"
        assert event.metadata["assistant_id"] == "5b0a4a08-133c-4146-9315-0984f8c6be80"

    def test_fallback_to_recording_url(self):
        payload = {
            "message": {
                "type": "end-of-call-report",
                "call": {"id": "x", "recordingUrl": "https://example.com/rec.mp3"},
                "artifact": {},
            }
        }
        event = parse_vapi_webhook(payload)
        assert event.recording_url == "https://example.com/rec.mp3"


# ---------------------------------------------------------------------------
# Retell
# ---------------------------------------------------------------------------

RETELL_PAYLOAD = {
    "event": "call_ended",
    "call": {
        "call_id": "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6",
        "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
        "agent_name": "My Agent",
        "direction": "inbound",
        "from_number": "+12137771234",
        "to_number": "+12137771235",
        "duration_ms": 15791,
        "disconnection_reason": "user_hangup",
        "transcript": "Agent: Hi! User: Help me.",
        "recording_url": "https://retellai.s3.amazonaws.com/recording.wav",
        "call_cost": {"combined_cost": 90},
    },
}


class TestRetellParser:
    def test_detects_retell(self):
        event = detect_and_parse_webhook(RETELL_PAYLOAD)
        assert event.platform == "retell"

    def test_parses_correctly(self):
        event = parse_retell_webhook(RETELL_PAYLOAD)
        assert event.call_id == "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6"
        assert event.recording_url == "https://retellai.s3.amazonaws.com/recording.wav"
        assert event.duration_ms == 15791
        assert event.metadata["agent_name"] == "My Agent"


# ---------------------------------------------------------------------------
# Bland.ai
# ---------------------------------------------------------------------------

BLAND_PAYLOAD = {
    "call_id": "12345678-1234-1234-1234-123456789012",
    "completed": True,
    "status": "completed",
    "concatenated_transcript": "user: Hello?\nassistant: This is a test call.",
    "transcripts": [
        {"user": "user", "text": "Hello?"},
        {"user": "assistant", "text": "This is a test call."},
    ],
    "corrected_duration": "11",
    "recording_url": "https://api.twilio.com/Recordings/RE456",
    "from": "+15559876543",
    "to": "+15551234567",
    "price": 0.017,
    "summary": "Brief test call.",
    "disposition_tag": "COMPLETED_ACTION",
}


class TestBlandParser:
    def test_detects_bland(self):
        event = detect_and_parse_webhook(BLAND_PAYLOAD)
        assert event.platform == "bland"

    def test_parses_correctly(self):
        event = parse_bland_webhook(BLAND_PAYLOAD)
        assert event.call_id == "12345678-1234-1234-1234-123456789012"
        assert event.recording_url == "https://api.twilio.com/Recordings/RE456"
        assert "Hello?" in event.transcript
        assert event.duration_ms == 11000
        assert event.metadata["price"] == 0.017

    def test_falls_back_to_transcripts_array(self):
        payload = {
            "call_id": "x",
            "completed": True,
            "transcripts": [
                {"user": "user", "text": "Hi"},
                {"user": "assistant", "text": "Hello!"},
            ],
            "corrected_duration": "5",
        }
        event = parse_bland_webhook(payload)
        assert "user: Hi" in event.transcript
        assert "assistant: Hello!" in event.transcript


# ---------------------------------------------------------------------------
# Bolna
# ---------------------------------------------------------------------------

BOLNA_PAYLOAD = {
    "id": 7432382142914,
    "agent_id": "3c90c3cc-0d44-4b50-8888-8dd25736052a",
    "status": "completed",
    "conversation_duration": 123,
    "total_cost": 123,
    "transcript": "Agent: Hello! User: I want to check my order.",
    "telephony_data": {
        "recording_url": "https://bolna-recordings.s3.amazonaws.com/rec.mp3",
        "from_number": "+1987654007",
        "to_number": "+10123456789",
        "call_type": "outbound",
        "provider": "twilio",
    },
    "extracted_data": {"order_id": "12345"},
}


class TestBolnaParser:
    def test_detects_bolna(self):
        event = detect_and_parse_webhook(BOLNA_PAYLOAD)
        assert event.platform == "bolna"

    def test_parses_correctly(self):
        event = parse_bolna_webhook(BOLNA_PAYLOAD)
        assert event.call_id == "7432382142914"
        assert event.recording_url == "https://bolna-recordings.s3.amazonaws.com/rec.mp3"
        assert event.duration_ms == 123000
        assert event.metadata["agent_id"] == "3c90c3cc-0d44-4b50-8888-8dd25736052a"
        assert event.metadata["extracted_data"]["order_id"] == "12345"


# ---------------------------------------------------------------------------
# Synthflow
# ---------------------------------------------------------------------------

SYNTHFLOW_PAYLOAD = {
    "call_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "agent_goodbye",
    "agent_id": "agent-123",
    "model_id": "model-456",
    "duration": 113,
    "transcript": "\nbot: Hey! Welcome!\nhuman: Hi, I need help.",
    "phone_number": "+1234567890",
    "collected_variables": {
        "user_name": {"value": "Julian", "collected": True},
    },
    "executed_actions": {
        "extract_info_email": {
            "results": {"user_email": "john@example.com"},
        }
    },
}


class TestSynthflowParser:
    def test_detects_synthflow(self):
        event = detect_and_parse_webhook(SYNTHFLOW_PAYLOAD)
        assert event.platform == "synthflow"

    def test_parses_correctly(self):
        event = parse_synthflow_webhook(SYNTHFLOW_PAYLOAD)
        assert event.call_id == "550e8400-e29b-41d4-a716-446655440000"
        assert event.duration_ms == 113000
        assert "bot: Hey!" in event.transcript
        assert event.metadata["collected_variables"]["user_name"]["value"] == "Julian"


# ---------------------------------------------------------------------------
# Air.ai
# ---------------------------------------------------------------------------

AIRAI_PAYLOAD = {
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
        "notes": "Prospect interested in demo.",
        "cachedLeadName": "Tyler",
    }
}


class TestAiraiParser:
    def test_detects_airai(self):
        event = detect_and_parse_webhook(AIRAI_PAYLOAD)
        assert event.platform == "airai"

    def test_parses_correctly(self):
        event = parse_airai_webhook(AIRAI_PAYLOAD)
        assert event.call_id == "CAec7g2x30425ba039a83ffb4286754983"
        assert event.recording_url == "https://api.twilio.com/Recordings/RE25a9z"
        assert event.duration_ms == 44000
        assert event.metadata["outcome"] == "Booked appointment"
        assert event.metadata["cached_lead_name"] == "Tyler"


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

GENERIC_PAYLOAD = {
    "event": "call.ended",
    "call_id": "generic-001",
    "recording_url": "https://example.com/rec.mp3",
    "transcript": "Agent: Hello. User: Hi.",
}


class TestGenericParser:
    def test_detects_generic(self):
        event = detect_and_parse_webhook(GENERIC_PAYLOAD)
        assert event.platform == "generic"

    def test_parses_correctly(self):
        event = parse_generic_webhook(GENERIC_PAYLOAD)
        assert event.call_id == "generic-001"
        assert event.recording_url == "https://example.com/rec.mp3"
