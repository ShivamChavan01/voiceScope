from pydantic import BaseModel
from typing import Optional


class AnalyzeResponse(BaseModel):
    run_id: str
    generated_at: str
    pipeline: dict
    transcript_meta: dict
    analysis: dict
    report: dict


class ErrorResponse(BaseModel):
    run_id: Optional[str] = None
    status: str = "failed"
    errors: list[str]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "voicescope"
    version: str = "1.0.0"


class WebhookEvent(BaseModel):
    """Normalized webhook event — all platforms convert to this."""

    platform: str
    event_type: str
    call_id: str
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    duration_ms: Optional[int] = None
    ended_reason: Optional[str] = None
    metadata: dict = {}
    raw: dict = {}


# ---------------------------------------------------------------------------
# Vapi
# ---------------------------------------------------------------------------


def parse_vapi_webhook(payload: dict) -> WebhookEvent:
    """Parse Vapi end-of-call-report into WebhookEvent."""
    message = payload.get("message", {})
    call = message.get("call", {})
    artifact = message.get("artifact", {})

    recording_url = None
    recording = artifact.get("recording", {})
    if recording:
        recording_url = recording.get("monoUrl") or recording.get("stereoUrl")
    if not recording_url:
        recording_url = call.get("recordingUrl")

    return WebhookEvent(
        platform="vapi",
        event_type=message.get("type", "end-of-call-report"),
        call_id=call.get("id", ""),
        recording_url=recording_url,
        transcript=artifact.get("transcript") or message.get("transcript"),
        duration_ms=_parse_vapi_duration(call) or _seconds_to_ms(message.get("durationSeconds")),
        ended_reason=message.get("endedReason"),
        metadata={
            "assistant_id": call.get("assistantId"),
            "org_id": call.get("orgId"),
            "status": call.get("status"),
            "cost": call.get("cost") or message.get("cost"),
            "summary": message.get("summary"),
        },
        raw=payload,
    )


def _parse_vapi_duration(call: dict) -> Optional[int]:
    started = call.get("startedAt")
    ended = call.get("endedAt")
    if started and ended:
        from datetime import datetime

        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            return int((e - s).total_seconds() * 1000)
        except Exception:
            return None
    return None


def _seconds_to_ms(seconds) -> Optional[int]:
    if seconds is None:
        return None
    try:
        return int(float(seconds) * 1000)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Retell
# ---------------------------------------------------------------------------


def parse_retell_webhook(payload: dict) -> WebhookEvent:
    """Parse Retell call_ended into WebhookEvent."""
    call = payload.get("call", {})

    return WebhookEvent(
        platform="retell",
        event_type=payload.get("event", "call_ended"),
        call_id=call.get("call_id", ""),
        recording_url=call.get("recording_url"),
        transcript=call.get("transcript"),
        duration_ms=call.get("duration_ms"),
        ended_reason=call.get("disconnection_reason"),
        metadata={
            "agent_id": call.get("agent_id"),
            "agent_name": call.get("agent_name"),
            "direction": call.get("direction"),
            "from_number": call.get("from_number"),
            "to_number": call.get("to_number"),
            "call_cost": call.get("call_cost", {}).get("combined_cost"),
        },
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Bland.ai
# ---------------------------------------------------------------------------


def parse_bland_webhook(payload: dict) -> WebhookEvent:
    """Parse Bland.ai call completed webhook into WebhookEvent."""
    transcript = payload.get("concatenated_transcript")
    if not transcript:
        transcripts = payload.get("transcripts", [])
        if transcripts:
            transcript = "\n".join(
                f"{t.get('user', 'unknown')}: {t.get('text', '')}" for t in transcripts
            )

    duration_ms = None
    corrected = payload.get("corrected_duration")
    if corrected is not None:
        try:
            duration_ms = int(float(corrected) * 1000)
        except (ValueError, TypeError):
            pass
    if duration_ms is None and payload.get("call_length"):
        duration_ms = int(float(payload["call_length"]) * 60 * 1000)

    return WebhookEvent(
        platform="bland",
        event_type="call.completed"
        if payload.get("completed")
        else payload.get("status", "call.completed"),
        call_id=payload.get("call_id", payload.get("c_id", "")),
        recording_url=payload.get("recording_url"),
        transcript=transcript,
        duration_ms=duration_ms,
        ended_reason=payload.get("disposition_tag") or payload.get("call_ended_by"),
        metadata={
            "batch_id": payload.get("batch_id"),
            "from_number": payload.get("from"),
            "to_number": payload.get("to"),
            "inbound": payload.get("inbound"),
            "price": payload.get("price"),
            "summary": payload.get("summary"),
            "answered_by": payload.get("answered_by"),
            "variables": payload.get("variables", {}),
        },
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Bolna
# ---------------------------------------------------------------------------


def parse_bolna_webhook(payload: dict) -> WebhookEvent:
    """Parse Bolna call completed webhook into WebhookEvent."""
    telephony = payload.get("telephony_data", {})

    return WebhookEvent(
        platform="bolna",
        event_type=payload.get("status", "completed"),
        call_id=str(payload.get("id", "")),
        recording_url=telephony.get("recording_url"),
        transcript=payload.get("transcript"),
        duration_ms=_seconds_to_ms(payload.get("conversation_duration")),
        ended_reason=payload.get("error_message") or payload.get("status"),
        metadata={
            "agent_id": payload.get("agent_id"),
            "batch_id": payload.get("batch_id"),
            "from_number": telephony.get("from_number"),
            "to_number": telephony.get("to_number"),
            "call_type": telephony.get("call_type"),
            "provider": telephony.get("provider"),
            "total_cost": payload.get("total_cost"),
            "extracted_data": payload.get("extracted_data"),
            "usage_breakdown": payload.get("usage_breakdown"),
        },
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Synthflow
# ---------------------------------------------------------------------------


def parse_synthflow_webhook(payload: dict) -> WebhookEvent:
    """Parse Synthflow call completed webhook into WebhookEvent."""
    return WebhookEvent(
        platform="synthflow",
        event_type=payload.get("status", "completed"),
        call_id=payload.get("call_id", ""),
        recording_url=payload.get("recording_url"),
        transcript=payload.get("transcript"),
        duration_ms=_seconds_to_ms(payload.get("duration")),
        ended_reason=payload.get("status"),
        metadata={
            "agent_id": payload.get("agent_id"),
            "model_id": payload.get("model_id"),
            "phone_number": payload.get("phone_number"),
            "collected_variables": payload.get("collected_variables"),
            "executed_actions": payload.get("executed_actions"),
        },
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Air.ai
# ---------------------------------------------------------------------------


def parse_airai_webhook(payload: dict) -> WebhookEvent:
    """Parse Air.ai POST_CALL_DATA webhook into WebhookEvent."""
    call = payload.get("call", {})

    return WebhookEvent(
        platform="airai",
        event_type="call.completed",
        call_id=call.get("sid", ""),
        recording_url=call.get("callRecordingUrl"),
        transcript=call.get("transcript"),
        duration_ms=_seconds_to_ms(call.get("duration")),
        ended_reason=call.get("llmAnsweredBy"),
        metadata={
            "from_number": call.get("fromNumber"),
            "to_number": call.get("toNumber"),
            "direction": call.get("direction"),
            "outcome": call.get("outcome"),
            "notes": call.get("notes"),
            "cached_lead_name": call.get("cachedLeadName"),
            "campaign_id": call.get("campaignId"),
        },
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Generic / Unknown
# ---------------------------------------------------------------------------


def parse_generic_webhook(payload: dict) -> WebhookEvent:
    """Parse a generic webhook payload (flat structure)."""
    return WebhookEvent(
        platform="generic",
        event_type=payload.get("event", payload.get("type", payload.get("status", "call.ended"))),
        call_id=payload.get("call_id", payload.get("id", "")),
        recording_url=payload.get("recording_url"),
        transcript=payload.get("transcript"),
        duration_ms=payload.get("duration_ms"),
        ended_reason=payload.get("ended_reason", payload.get("disconnection_reason")),
        metadata=payload.get("metadata", {}),
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def detect_and_parse_webhook(payload: dict) -> WebhookEvent:
    """Auto-detect platform and parse webhook payload.

    Detection order:
    1. Vapi — has payload.message.type in (end-of-call-report, status-update)
    2. Retell — has event in (call_ended, call_analyzed) + call.call_id
    3. Bland — has concatenated_transcript or transcripts array
    4. Bolna — has telephony_data.recording_url + conversation_duration
    5. Synthflow — has collected_variables + executed_actions
    6. Air.ai — has call.sid + call.callRecordingUrl
    7. Generic fallback
    """

    # Vapi
    if "message" in payload and isinstance(payload["message"], dict):
        msg_type = payload["message"].get("type", "")
        if msg_type in ("end-of-call-report", "status-update"):
            return parse_vapi_webhook(payload)

    # Retell
    if "event" in payload:
        event_val = payload["event"]
        if event_val in ("call_ended", "call_analyzed", "call_started"):
            if "call" in payload and isinstance(payload["call"], dict):
                return parse_retell_webhook(payload)

    # Bland.ai
    if "concatenated_transcript" in payload or (
        "transcripts" in payload and isinstance(payload["transcripts"], list)
    ):
        return parse_bland_webhook(payload)

    # Bolna
    if "telephony_data" in payload and isinstance(payload["telephony_data"], dict):
        return parse_bolna_webhook(payload)

    # Synthflow
    if "collected_variables" in payload or "executed_actions" in payload:
        return parse_synthflow_webhook(payload)

    # Air.ai
    if "call" in payload and isinstance(payload["call"], dict):
        call = payload["call"]
        if "sid" in call and "callRecordingUrl" in call:
            return parse_airai_webhook(payload)

    # Generic
    return parse_generic_webhook(payload)
