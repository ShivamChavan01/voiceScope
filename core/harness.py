"""
VoiceScope Validation Harness — 7-layer validation for LLM outputs.

Layer 1: Schema Validation (Pydantic)
Layer 2: Citation Verification
Layer 3: Cross-Check (internal consistency)
Layer 4: Fact Extraction & Verification
Layer 5: Sentiment Consistency Check
Layer 6: Outcome Evidence Check
Layer 7: Escalation Signal Verification
"""

import time
import hashlib
import json
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class OutcomeType(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    ESCALATED = "escalated"


class AnalysisOutput(BaseModel):
    intent: str = ""
    sentiment_arc: str = ""
    hallucination_detected: bool = False
    hallucination_evidence: Optional[str] = None
    outcome: str = ""
    escalation_signal: bool = False
    findings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def validate_enums(cls, data):
        if isinstance(data, dict):
            # Validate sentiment_arc
            valid_sentiments = {s.value for s in SentimentType}
            sentiment = data.get("sentiment_arc", "")
            if sentiment and sentiment not in valid_sentiments:
                raise ValueError(f"sentiment_arc must be one of {valid_sentiments}, got '{sentiment}'")
            # Validate outcome
            valid_outcomes = {o.value for o in OutcomeType}
            outcome = data.get("outcome", "")
            if outcome and outcome not in valid_outcomes:
                raise ValueError(f"outcome must be one of {valid_outcomes}, got '{outcome}'")
            # Validate hallucination_detected is bool
            hd = data.get("hallucination_detected")
            if hd is not None and not isinstance(hd, bool):
                raise ValueError(f"hallucination_detected must be bool, got {type(hd).__name__}")
        return data


class ReportOutput(BaseModel):
    quality_score: int = 50
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def validate_quality_score(self):
        if not isinstance(self.quality_score, (int, float)):
            try:
                self.quality_score = int(self.quality_score)
            except (ValueError, TypeError):
                self.quality_score = 50
        self.quality_score = max(0, min(100, int(self.quality_score)))
        return self


class ValidationResult(BaseModel):
    passed: bool = True
    confidence: float = 1.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    layer_scores: dict[str, float] = Field(default_factory=dict)


class HarnessResult(BaseModel):
    truth_score: float = 0.0
    confidence: str = "unknown"
    validation_passed: bool = True
    validation_errors: list[str] = Field(default_factory=list)
    layer_scores: dict[str, float] = Field(default_factory=dict)
    raw_output: dict = Field(default_factory=dict)
    validated_output: dict = Field(default_factory=dict)
    response_time_ms: float = 0.0
    token_usage: dict = Field(default_factory=dict)
    duplicate_hash: str = ""
    audio_quality_score: Optional[float] = None


class ValidationHarness:
    """7-layer validation harness for LLM outputs."""

    def __init__(self):
        self._seen_hashes: dict[str, float] = {}
        self._calibration_data: list[dict] = []

    def validate_analysis(self, raw_output: dict, transcript: str = "") -> HarnessResult:
        """Run all applicable validation layers on analysis output."""
        result = HarnessResult(raw_output=raw_output)
        layer_scores = {}

        # Layer 1: Schema Validation
        schema_result = self._schema_validate_analysis(raw_output)
        layer_scores["schema"] = schema_result.confidence
        if not schema_result.passed:
            result.validation_errors.extend(schema_result.errors)
            result.validation_passed = False

        # Layer 2: Citation Verification (if transcript available)
        if transcript and raw_output.get("findings"):
            from core.citations import CitationVerifier
            cite_result = CitationVerifier().verify(transcript, raw_output["findings"])
            layer_scores["citations"] = cite_result.coverage
            if cite_result.unmatched:
                result.validation_errors.extend(
                    [f"unmatched finding: {f}" for f in cite_result.unmatched]
                )

        # Layer 3: Cross-Check (internal consistency of analysis fields)
        from core.cross_check import CrossChecker
        cross_result = CrossChecker().check(raw_output)
        layer_scores["cross_check"] = cross_result.score
        if not cross_result.consistent:
            result.validation_errors.extend(cross_result.inconsistencies)

        # Layer 4: Fact Extraction & Verification (if transcript available)
        if transcript:
            from core.facts import FactExtractor
            fact_result = FactExtractor().verify(transcript, raw_output)
            layer_scores["facts"] = fact_result.accuracy
            if fact_result.contradictions:
                result.validation_errors.extend(
                    [f"contradiction: {c}" for c in fact_result.contradictions]
                )

        # Layer 5: Sentiment Consistency (if transcript available)
        if transcript:
            from core.sentiment_check import SentimentCheck
            sent_result = SentimentCheck().check(transcript, raw_output.get("sentiment_arc", ""))
            layer_scores["sentiment_consistency"] = sent_result.consistency_score
            if not sent_result.consistent:
                result.validation_errors.append(
                    f"sentiment mismatch: transcript suggests {sent_result.suggested_sentiment}, "
                    f"LLM reported {raw_output.get('sentiment_arc')}"
                )

        # Layer 6: Outcome Evidence (if transcript available)
        if transcript:
            from core.outcome_check import OutcomeCheck
            out_result = OutcomeCheck().check(transcript, raw_output.get("outcome", ""))
            layer_scores["outcome_evidence"] = out_result.evidence_score
            if not out_result.has_evidence:
                result.validation_errors.append(
                    f"outcome '{raw_output.get('outcome')}' lacks evidence in transcript"
                )

        # Layer 7: Escalation Verification (if transcript available)
        if transcript:
            from core.outcome_check import OutcomeCheck
            esc_result = OutcomeCheck().check_escalation(transcript, raw_output.get("escalation_signal", False))
            layer_scores["escalation"] = esc_result.evidence_score
            if raw_output.get("escalation_signal") and not esc_result.has_evidence:
                result.validation_errors.append(
                    "escalation_signal=True but no escalation markers in transcript"
                )

        # Layer 10: Duplicate Detection
        content_hash = hashlib.sha256(json.dumps(raw_output, sort_keys=True, default=str).encode()).hexdigest()
        result.duplicate_hash = content_hash
        if content_hash in self._seen_hashes:
            time_diff = time.time() - self._seen_hashes[content_hash]
            if time_diff < 300:  # within 5 minutes
                result.validation_errors.append(f"duplicate analysis detected (hash={content_hash[:8]})")
                layer_scores["duplicate"] = 0.0
            else:
                layer_scores["duplicate"] = 1.0
        else:
            layer_scores["duplicate"] = 1.0
        self._seen_hashes[content_hash] = time.time()

        # Evict old hashes (keep last 1000)
        if len(self._seen_hashes) > 1000:
            oldest = sorted(self._seen_hashes, key=self._seen_hashes.get)[:500]
            for k in oldest:
                del self._seen_hashes[k]

        # Compute truth score
        result.layer_scores = layer_scores
        result.truth_score = self._compute_truth_score(layer_scores)
        result.confidence = self._score_to_confidence(result.truth_score)
        result.validated_output = raw_output

        return result

    def validate_report(self, raw_output: dict) -> HarnessResult:
        """Validate report output."""
        result = HarnessResult(raw_output=raw_output)
        schema_result = self._schema_validate_report(raw_output)
        result.layer_scores["schema"] = schema_result.confidence
        if not schema_result.passed:
            result.validation_errors.extend(schema_result.errors)
            result.validation_passed = False
        result.truth_score = schema_result.confidence
        result.confidence = self._score_to_confidence(result.truth_score)
        result.validated_output = raw_output
        return result

    def validate_pipeline(self, ctx) -> HarnessResult:
        """Run full harness on pipeline context. Returns aggregated result."""
        ctx.report = ctx.report or {}
        analysis = ctx.report.get("analysis", {})
        transcript = getattr(ctx, "raw_transcript", "") or ""

        result = self.validate_analysis(analysis, transcript)

        # Layer 8: Response time tracking
        if hasattr(ctx, "llm_response_time_ms"):
            result.response_time_ms = ctx.llm_response_time_ms
            if ctx.llm_response_time_ms > 10000:
                result.validation_errors.append("LLM response time >10s (model may be struggling)")

        # Layer 9: Token usage tracking
        if hasattr(ctx, "llm_token_usage"):
            result.token_usage = ctx.llm_token_usage or {}
            total_tokens = result.token_usage.get("input_tokens", 0) + result.token_usage.get("output_tokens", 0)
            if total_tokens > 10000:
                result.validation_errors.append(f"abnormal token usage: {total_tokens} tokens")

        # Store in context
        ctx.report["harness"] = result.model_dump()
        return result

    def _schema_validate_analysis(self, raw_output: dict) -> ValidationResult:
        """Layer 1: Schema validation for analysis output."""
        if not raw_output:
            return ValidationResult(
                passed=False,
                confidence=0.0,
                errors=["empty analysis output"],
            )
        try:
            AnalysisOutput(**raw_output)
            return ValidationResult(passed=True, confidence=1.0)
        except Exception as e:
            return ValidationResult(
                passed=False,
                confidence=0.3,
                errors=[f"schema validation failed: {str(e)}"],
            )

    def _schema_validate_report(self, raw_output: dict) -> ValidationResult:
        """Layer 1: Schema validation for report output."""
        try:
            ReportOutput(**raw_output)
            return ValidationResult(passed=True, confidence=1.0)
        except Exception as e:
            return ValidationResult(
                passed=False,
                confidence=0.3,
                errors=[f"schema validation failed: {str(e)}"],
            )

    def _compute_truth_score(self, layer_scores: dict[str, float]) -> float:
        """Weighted average of all layer scores."""
        if not layer_scores:
            return 0.0
        weights = {
            "schema": 0.25,
            "citations": 0.15,
            "cross_check": 0.10,
            "facts": 0.15,
            "sentiment_consistency": 0.10,
            "outcome_evidence": 0.10,
            "escalation": 0.05,
            "duplicate": 0.05,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for layer, score in layer_scores.items():
            w = weights.get(layer, 0.05)
            weighted_sum += score * w
            total_weight += w
        return round(weighted_sum / total_weight if total_weight > 0 else 0.0, 4)

    def _score_to_confidence(self, score: float) -> str:
        if score >= 0.85:
            return "high"
        elif score >= 0.70:
            return "medium"
        elif score >= 0.50:
            return "low"
        return "very_low"

    def get_summary(self) -> dict:
        """Get summary of harness state for API response."""
        return {
            "total_analyses": len(self._seen_hashes),
            "calibration_samples": len(self._calibration_data),
        }
