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


class WebhookPayload(BaseModel):
    event: str
    call_id: str
    recording_url: str
    metadata: dict = {}
