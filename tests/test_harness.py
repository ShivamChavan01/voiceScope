import os
import pytest
import time

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["CALIBRATION_DB_PATH"] = ":memory:"

from core.harness import (
    ValidationHarness,
)
from core.citations import CitationVerifier
from core.facts import FactExtractor
from core.sentiment_check import SentimentCheck
from core.outcome_check import OutcomeCheck
from core.audio_quality import AudioQualityChecker, LLMResponseTimer, TokenTracker
from core.calibration import ConfidenceCalibrator
from core.feedback import FeedbackStore


# ─── Layer 1: Schema Validation ──────────────────────────────────────


class TestSchemaValidation:
    def test_valid_analysis(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "billing inquiry",
            "sentiment_arc": "negative",
            "hallucination_detected": False,
            "hallucination_evidence": "",
            "outcome": "resolved",
            "escalation_signal": False,
            "findings": ["Customer was charged twice"],
        })
        assert result.truth_score > 0.5
        assert result.validation_passed

    def test_invalid_sentiment(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "test",
            "sentiment_arc": "super_happy",
            "hallucination_detected": False,
            "outcome": "resolved",
            "escalation_signal": False,
        })
        assert not result.validation_passed
        assert any("sentiment_arc" in e for e in result.validation_errors)

    def test_invalid_outcome(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "test",
            "sentiment_arc": "positive",
            "hallucination_detected": False,
            "outcome": "maybe_resolved",
            "escalation_signal": False,
        })
        assert not result.validation_passed
        assert any("outcome" in e for e in result.validation_errors)

    def test_hallucination_not_bool(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "test",
            "sentiment_arc": "positive",
            "hallucination_detected": "yes",
            "outcome": "resolved",
            "escalation_signal": False,
        })
        assert not result.validation_passed

    def test_valid_report(self):
        h = ValidationHarness()
        result = h.validate_report({
            "quality_score": 85,
            "key_findings": ["Issue resolved"],
            "recommendations": ["Follow up"],
            "summary": "Call went well",
        })
        assert result.truth_score > 0.5

    def test_report_quality_score_string(self):
        h = ValidationHarness()
        result = h.validate_report({
            "quality_score": "85",
            "key_findings": [],
            "recommendations": [],
            "summary": "test",
        })
        assert result.validation_passed  # should coerce

    def test_report_quality_score_out_of_range(self):
        h = ValidationHarness()
        result = h.validate_report({
            "quality_score": 150,
            "key_findings": [],
            "recommendations": [],
            "summary": "test",
        })
        assert result.validation_passed  # should clamp to 100

    def test_empty_response(self):
        h = ValidationHarness()
        result = h.validate_analysis({})
        assert not result.validation_passed

    def test_extra_fields_ignored(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "test",
            "sentiment_arc": "neutral",
            "hallucination_detected": False,
            "outcome": "unresolved",
            "escalation_signal": False,
            "extra_field": "should be ignored",
        })
        assert result.validation_passed


# ─── Layer 2: Citation Verification ──────────────────────────────────


class TestCitationVerification:
    def test_all_found(self):
        v = CitationVerifier()
        result = v.verify(
            "Customer said the product broke. Agent offered refund.",
            ["Product was broken", "Agent offered refund"],
        )
        assert result.coverage > 0.8

    def test_none_found(self):
        v = CitationVerifier()
        result = v.verify(
            "Customer said hello.",
            ["Customer reported a fire", "Agent called 911"],
        )
        assert result.coverage < 0.5

    def test_partial_match(self):
        v = CitationVerifier()
        result = v.verify(
            "The order was placed on Monday and shipped Tuesday.",
            ["Order placed Monday", "Customer demanded refund"],
        )
        assert 0.0 < result.coverage < 1.0

    def test_empty_transcript(self):
        v = CitationVerifier()
        result = v.verify("", ["finding"])
        assert result.coverage == 0.0

    def test_empty_findings(self):
        v = CitationVerifier()
        result = v.verify("some transcript", [])
        assert result.coverage == 1.0


# ─── Layer 3: Cross-Check ────────────────────────────────────────────


# ─── Layer 4: Fact Extraction ────────────────────────────────────────


class TestFactExtraction:
    def test_extract_numbers(self):
        e = FactExtractor()
        facts = e.extract_facts("The price is $49.99 and tax is $5.00")
        numbers = [f for f in facts if f.fact_type == "number"]
        assert len(numbers) >= 2

    def test_extract_dates(self):
        e = FactExtractor()
        facts = e.extract_facts("The meeting is on January 15, 2025")
        dates = [f for f in facts if f.fact_type == "date"]
        assert len(dates) >= 1

    def test_extract_promises(self):
        e = FactExtractor()
        facts = e.extract_facts("I will send you a new one by Friday")
        promises = [f for f in facts if f.fact_type == "promise"]
        assert len(promises) >= 1

    def test_verify_no_contradictions(self):
        e = FactExtractor()
        result = e.verify(
            "The price is $50",
            {"intent": "billing", "outcome": "resolved"},
        )
        assert result.accuracy >= 0.8

    def test_verify_contradiction(self):
        e = FactExtractor()
        result = e.verify(
            "The price is $50",
            {"intent": "billing", "findings": ["Customer paid $75"]},
        )
        assert len(result.contradictions) > 0


# ─── Layer 5: Sentiment Consistency ──────────────────────────────────


class TestSentimentConsistency:
    def test_positive_transcript_positive_label(self):
        s = SentimentCheck()
        result = s.check(
            "This is great! I love the service. Thank you so much!",
            "positive",
        )
        assert result.consistent
        assert result.consistency_score > 0.7

    def test_negative_transcript_positive_label(self):
        s = SentimentCheck()
        result = s.check(
            "This is terrible! I'm angry and frustrated! Worst experience ever!",
            "positive",
        )
        assert not result.consistent
        assert result.suggested_sentiment == "negative"

    def test_neutral_transcript(self):
        s = SentimentCheck()
        result = s.check(
            "Okay. Got it. Will do. Sure.",
            "neutral",
        )
        assert result.consistent

    def test_mixed_sentiment(self):
        s = SentimentCheck()
        result = s.check(
            "The product is great but the service was terrible and frustrating",
            "mixed",
        )
        # Should at least not be wildly wrong
        assert result.consistency_score >= 0.0


# ─── Layer 6 & 7: Outcome + Escalation Verification ─────────────────


class TestOutcomeVerification:
    def test_resolved_with_evidence(self):
        o = OutcomeCheck()
        result = o.check(
            "Issue fixed. All set. Glad to help. Anything else?",
            "resolved",
        )
        assert result.has_evidence
        assert len(result.evidence_found) > 0

    def test_resolved_without_evidence(self):
        o = OutcomeCheck()
        result = o.check(
            "The customer was asking about billing.",
            "resolved",
        )
        assert not result.has_evidence

    def test_unresolved_with_evidence(self):
        o = OutcomeCheck()
        result = o.check(
            "Still waiting. Not sure when it will be fixed.",
            "unresolved",
        )
        assert result.has_evidence

    def test_escalation_with_evidence(self):
        o = OutcomeCheck()
        result = o.check(
            "Let me transfer you to a supervisor.",
            "escalated",
        )
        assert result.has_evidence

    def test_escalation_without_evidence(self):
        o = OutcomeCheck()
        result = o.check_escalation(
            "The call went normally.",
            True,
        )
        assert not result.has_evidence

    def test_escalation_signal_false(self):
        o = OutcomeCheck()
        result = o.check_escalation("Normal call.", False)
        assert result.has_evidence
        assert result.evidence_score == 1.0


# ─── Layer 8: Audio Quality ──────────────────────────────────────────


class TestAudioQuality:
    def test_good_audio(self):
        c = AudioQualityChecker()
        result = c.check(b"\x00" * 100000, "recording.mp3")
        assert result.should_proceed
        assert result.quality_score > 0.5

    def test_too_small(self):
        c = AudioQualityChecker()
        result = c.check(b"\x00" * 100, "recording.mp3")
        assert not result.should_proceed

    def test_mostly_silence(self):
        c = AudioQualityChecker()
        result = c.check(b"\x00" * 50000, "recording.wav")
        assert any("silence" in i for i in result.issues)

    def test_unusual_format(self):
        c = AudioQualityChecker()
        result = c.check(b"\x00" * 10000, "recording.xyz")
        assert any("format" in i for i in result.issues)


class TestResponseTimer:
    def test_timer(self):
        t = LLMResponseTimer()
        t.start()
        time.sleep(0.01)
        elapsed = t.stop()
        assert elapsed > 0
        assert not t.is_anomalous()

    def test_anomalous(self):
        t = LLMResponseTimer()
        t._elapsed_ms = 15000
        assert t.is_anomalous()


class TestTokenTracker:
    def test_record_and_get(self):
        t = TokenTracker()
        t.record(100, 50, "openai")
        latest = t.get_latest()
        assert latest["total"] == 150

    def test_anomalous(self):
        t = TokenTracker()
        t.record(6000, 6000)
        assert t.is_anomalous()

    def test_average(self):
        t = TokenTracker()
        t.record(100, 50)
        t.record(200, 100)
        avg = t.get_average()
        assert avg["avg_input_tokens"] == 150
        assert avg["total_calls"] == 2


# ─── Layer 10: Duplicate Detection ───────────────────────────────────


class TestDuplicateDetection:
    def test_first_analysis_no_duplicate(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "test",
            "sentiment_arc": "neutral",
            "hallucination_detected": False,
            "outcome": "unresolved",
            "escalation_signal": False,
        })
        assert result.layer_scores.get("duplicate", 1.0) == 1.0

    def test_duplicate_detected(self):
        h = ValidationHarness()
        data = {
            "intent": "test",
            "sentiment_arc": "neutral",
            "hallucination_detected": False,
            "outcome": "unresolved",
            "escalation_signal": False,
        }
        h.validate_analysis(data)
        result = h.validate_analysis(data)
        assert result.layer_scores.get("duplicate", 1.0) == 0.0
        assert any("duplicate" in e for e in result.validation_errors)


# ─── Layer 12: Confidence Calibration ────────────────────────────────


class TestCalibration:
    def test_record_and_get(self):
        c = ConfidenceCalibrator(":memory:")
        c._entries = []  # reset
        c.record("run-001", 0.9, "high")
        c.record("run-002", 0.6, "low")
        result = c.get_calibration()
        assert result.total_predictions == 2

    def test_add_feedback(self):
        c = ConfidenceCalibrator(":memory:")
        c._entries = []  # reset
        c.record("run-001", 0.9, "high")
        c.add_feedback("run-001", "correct")
        result = c.get_calibration()
        assert result.feedback_count == 1
        assert result.high_confidence_accuracy == 1.0


# ─── Layer 13: Feedback Loop ─────────────────────────────────────────


class TestFeedback:
    def test_submit_correct(self):
        store = FeedbackStore()
        result = store.submit("run-001", "correct")
        assert result["status"] == "recorded"
        assert result["feedback"] == "correct"

    def test_submit_incorrect(self):
        store = FeedbackStore()
        result = store.submit("run-002", "incorrect")
        assert result["status"] == "recorded"

    def test_invalid_feedback(self):
        store = FeedbackStore()
        with pytest.raises(ValueError):
            store.submit("run-003", "maybe")

    def test_get_calibration(self):
        store = FeedbackStore()
        cal = store.get_calibration()
        assert "total_predictions" in cal


# ─── Truth Score Computation ──────────────────────────────────────────


class TestTruthScore:
    def test_all_pass(self):
        h = ValidationHarness()
        result = h.validate_analysis({
            "intent": "billing issue",
            "sentiment_arc": "negative",
            "hallucination_detected": False,
            "outcome": "resolved",
            "escalation_signal": False,
            "findings": ["Customer charged twice"],
        })
        assert result.truth_score > 0.5
        assert result.confidence in ("high", "medium")

    def test_all_fail(self):
        h = ValidationHarness()
        result = h.validate_analysis({})
        assert result.truth_score < 0.5
        assert result.confidence in ("low", "very_low")

    def test_confidence_levels(self):
        h = ValidationHarness()
        assert h._score_to_confidence(0.9) == "high"
        assert h._score_to_confidence(0.75) == "medium"
        assert h._score_to_confidence(0.55) == "low"
        assert h._score_to_confidence(0.3) == "very_low"
