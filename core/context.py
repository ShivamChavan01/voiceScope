from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime, timezone


class PipelineContext(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    raw_transcript: Optional[str] = None
    transcript_speakers: Optional[list[dict]] = None
    audio_duration_seconds: Optional[float] = None
    language_detected: Optional[str] = None

    intent: Optional[str] = None
    sentiment_arc: Optional[str] = None
    hallucination_detected: Optional[bool] = None
    hallucination_evidence: Optional[str] = None
    outcome: Optional[str] = None
    escalation_signal: Optional[bool] = None

    word_count: Optional[int] = None
    chunk_count: Optional[int] = None

    report: Optional[dict] = None

    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    errors: list[str] = Field(default_factory=list)
    stages_completed: list[str] = Field(default_factory=list)

    def mark_stage(self, stage: str):
        self.stages_completed.append(stage)

    def add_error(self, stage: str, message: str):
        self.errors.append(f"[{stage}] {message}")
