from pydantic import BaseModel
from typing import Optional


class ProviderInfo(BaseModel):
    name: str
    model: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class AnalysisResult(BaseModel):
    intent: Optional[str] = None
    sentiment_arc: Optional[str] = None
    hallucination_detected: Optional[bool] = None
    hallucination_evidence: Optional[str] = None
    outcome: Optional[str] = None
    escalation_signal: Optional[bool] = None


class ReportInfo(BaseModel):
    executive_summary: Optional[str] = None
    quality_score: Optional[int] = None
    key_findings: list[str] = []
    recommendations: list[str] = []


class AnalysisReport(BaseModel):
    run_id: str
    generated_at: str
    provider: ProviderInfo
    transcript_meta: dict
    analysis: AnalysisResult
    report: ReportInfo
    conversation_flow: Optional[dict] = None
    evaluation: Optional[dict] = None


class BatchResult(BaseModel):
    batch_id: str
    status: str
    total: int
    completed: int
    failed: int
