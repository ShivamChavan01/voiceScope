from pydantic import BaseModel
from typing import Optional
from utils.logger import logger


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
    version: str = "2.0.0"


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
# Generic field discovery — works with ANY platform
# ---------------------------------------------------------------------------

# Keys to search for, ordered by likelihood. Case-insensitive matching.
_CALL_ID_KEYS = {"call_id", "callId", "callid", "id", "sid", "call_sid", "callSid"}
_RECORDING_URL_KEYS = {
    "recording_url",
    "recordingUrl",
    "recordinguri",
    "recording_uri",
    "callRecordingUrl",
    "call_recording_url",
    "monoUrl",
    "mono_url",
    "stereoUrl",
    "stereo_url",
    "audio_url",
    "audioUrl",
    "url",
    "src",
    "audio",
    "file_url",
    "fileUrl",
    "download_url",
    "downloadUrl",
    "media_url",
    "mediaUrl",
}
_TRANSCRIPT_KEYS = {
    "transcript",
    "transcripts",
    "concatenated_transcript",
    "transcript_text",
    "transcriptText",
    "full_transcript",
    "callTranscript",
    "call_transcript",
    "conversation_transcript",
}
_DURATION_KEYS = {
    "duration",
    "duration_ms",
    "durationMs",
    "duration_seconds",
    "durationSeconds",
    "call_length",
    "callLength",
    "conversation_duration",
    "conversationDuration",
    "corrected_duration",
    "correctedDuration",
    "total_duration",
    "totalDuration",
    "length",
    "callDuration",
    "call_duration",
    "time_seconds",
    "timeSeconds",
}
_EVENT_KEYS = {"event", "type", "status", "event_type", "eventType", "action"}
_ENDED_REASON_KEYS = {
    "ended_reason",
    "endedReason",
    "disconnection_reason",
    "disconnectionReason",
    "end_reason",
    "endReason",
    "hangup_reason",
    "hangupReason",
    "disposition_tag",
    "dispositionTag",
    "error_message",
    "call_ended_by",
}


def _deep_find(data: dict, keys: set[str], max_depth: int = 4):
    """Search nested dict for any of the given keys. Returns first match."""
    if max_depth <= 0:
        return None
    for key in keys:
        if key in data:
            return data[key]
    for val in data.values():
        if isinstance(val, dict):
            result = _deep_find(val, keys, max_depth - 1)
            if result is not None:
                return result
    return None


def _deep_find_str(data: dict, keys: set[str], max_depth: int = 4) -> Optional[str]:
    val = _deep_find(data, keys, max_depth)
    if isinstance(val, str) and val.strip():
        return val
    return None


def _deep_find_url(data: dict, keys: set[str], max_depth: int = 4) -> Optional[str]:
    val = _deep_find(data, keys, max_depth)
    if isinstance(val, str) and val.startswith("http"):
        return val
    return None


def _deep_find_duration_ms(data: dict, keys: set[str], max_depth: int = 4) -> Optional[int]:
    val = _deep_find(data, keys, max_depth)
    if val is None:
        return None
    if isinstance(val, (int, float)):
        # If value > 10000, likely already ms. If < 10000, likely seconds.
        if val > 10000:
            return int(val)
        return int(val * 1000)
    if isinstance(val, str):
        try:
            f = float(val)
            if f > 10000:
                return int(f)
            return int(f * 1000)
        except ValueError:
            pass
    return None


def _build_transcript(data: dict, max_depth: int = 4) -> Optional[str]:
    """Try to find or build a transcript from the payload."""
    # Direct string field
    direct = _deep_find_str(data, _TRANSCRIPT_KEYS, max_depth)
    if direct and "\n" in direct:
        return direct
    if direct:
        return direct

    # Bland-style transcripts array
    transcripts = _deep_find(data, {"transcripts"}, max_depth)
    if isinstance(transcripts, list) and transcripts:
        parts = []
        for t in transcripts:
            if isinstance(t, dict):
                role = t.get("user") or t.get("role") or t.get("speaker") or "unknown"
                text = t.get("text") or t.get("message") or t.get("content") or ""
                if text:
                    parts.append(f"{role}: {text}")
        if parts:
            return "\n".join(parts)

    # messages array (Vapi-style)
    messages = _deep_find(data, {"messages"}, max_depth)
    if isinstance(messages, list) and messages:
        parts = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role") or m.get("speaker") or "unknown"
                text = m.get("message") or m.get("text") or m.get("content") or ""
                if text:
                    parts.append(f"{role}: {text}")
        if parts:
            return "\n".join(parts)

    return None


def parse_generic_webhook(payload: dict) -> WebhookEvent:
    """Universal parser — discovers fields from any payload structure.

    Searches the entire payload recursively for common field names.
    Works with flat, nested, or deeply nested payloads from any platform.
    """
    call_id = _deep_find_str(payload, _CALL_ID_KEYS) or ""
    recording_url = _deep_find_url(payload, _RECORDING_URL_KEYS)
    transcript = _build_transcript(payload)
    duration_ms = _deep_find_duration_ms(payload, _DURATION_KEYS)
    event_type = _deep_find_str(payload, _EVENT_KEYS) or "call.ended"
    ended_reason = _deep_find_str(payload, _ENDED_REASON_KEYS)

    if not call_id:
        logger.warning("[WebhookParser] no call_id found in payload — using empty string")

    return WebhookEvent(
        platform="generic",
        event_type=event_type,
        call_id=call_id,
        recording_url=recording_url,
        transcript=transcript,
        duration_ms=duration_ms,
        ended_reason=ended_reason,
        metadata={"discovered_fields": True},
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Known platform parsers (extract richer metadata than generic)
# ---------------------------------------------------------------------------


def _seconds_to_ms(seconds) -> Optional[int]:
    if seconds is None:
        return None
    try:
        return int(float(seconds) * 1000)
    except (ValueError, TypeError):
        return None


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

    started = call.get("startedAt")
    ended = call.get("endedAt")
    duration_ms = None
    if started and ended:
        from datetime import datetime

        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            duration_ms = int((e - s).total_seconds() * 1000)
        except Exception:
            pass
    if duration_ms is None:
        duration_ms = _seconds_to_ms(message.get("durationSeconds"))

    return WebhookEvent(
        platform="vapi",
        event_type=message.get("type", "end-of-call-report"),
        call_id=call.get("id", ""),
        recording_url=recording_url,
        transcript=artifact.get("transcript") or message.get("transcript"),
        duration_ms=duration_ms,
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
# Auto-detection
# ---------------------------------------------------------------------------


def detect_and_parse_webhook(payload: dict) -> WebhookEvent:
    """Auto-detect platform and parse webhook payload.

    Known platforms get rich metadata extraction.
    Unknown platforms fall through to the universal generic parser
    which recursively discovers fields from any payload structure.
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

    # Universal generic — discovers fields from ANY structure
    event = parse_generic_webhook(payload)
    if not event.recording_url:
        logger.warning(
            f"[WebhookParser] generic parser found no recording_url — "
            f"call_id={event.call_id}, keys={list(payload.keys())[:10]}"
        )
    return event
