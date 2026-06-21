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
        transcript=artifact.get("transcript"),
        duration_ms=_parse_vapi_duration(call),
        ended_reason=message.get("endedReason"),
        metadata={
            "assistant_id": call.get("assistantId"),
            "org_id": call.get("orgId"),
            "status": call.get("status"),
            "cost": call.get("cost"),
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


def parse_generic_webhook(payload: dict) -> WebhookEvent:
    """Parse a generic webhook payload (flat structure)."""
    return WebhookEvent(
        platform="generic",
        event_type=payload.get("event", payload.get("type", "call.ended")),
        call_id=payload.get("call_id", payload.get("id", "")),
        recording_url=payload.get("recording_url"),
        transcript=payload.get("transcript"),
        duration_ms=payload.get("duration_ms"),
        ended_reason=payload.get("ended_reason", payload.get("disconnection_reason")),
        metadata=payload.get("metadata", {}),
        raw=payload,
    )


def detect_and_parse_webhook(payload: dict) -> WebhookEvent:
    """Auto-detect platform and parse webhook payload."""
    if "message" in payload and isinstance(payload["message"], dict):
        msg_type = payload["message"].get("type", "")
        if msg_type in ("end-of-call-report", "status-update"):
            return parse_vapi_webhook(payload)

    if "event" in payload:
        event_val = payload["event"]
        if event_val in ("call_ended", "call_analyzed", "call_started"):
            return parse_retell_webhook(payload)
        if "call" in payload and isinstance(payload["call"], dict):
            return parse_retell_webhook(payload)

    if "call_id" in payload or "recording_url" in payload:
        return parse_generic_webhook(payload)

    return parse_generic_webhook(payload)
