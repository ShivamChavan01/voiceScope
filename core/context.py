from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime


class PipelineContext(BaseModel):
    """Shared context object passed through all 3 agents in the pipeline."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Stage 1 — Transcription Agent output
    raw_transcript: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    language_detected: Optional[str] = None

    # Stage 2 — Analysis Agent output
    intent: Optional[str] = None
    sentiment_arc: Optional[str] = None          # positive / negative / mixed / neutral
    hallucination_detected: Optional[bool] = None
    hallucination_evidence: Optional[str] = None
    outcome: Optional[str] = None                # resolved / unresolved / escalated
    escalation_signal: Optional[bool] = None

    # Stage 3 — Report Agent output
    report: Optional[dict] = None

    # Pipeline metadata
    errors: list[str] = Field(default_factory=list)
    stages_completed: list[str] = Field(default_factory=list)

    def mark_stage(self, stage: str):
        self.stages_completed.append(stage)

    def add_error(self, stage: str, message: str):
        self.errors.append(f"[{stage}] {message}")
