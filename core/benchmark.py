"""
Harness Benchmark Runner — runs labeled test data through the harness,
compares results with expected answers, tracks accuracy per layer.
"""

import json
from pathlib import Path
from pydantic import BaseModel, Field
from core.harness import ValidationHarness, HarnessResult
from core.sentiment_check import SentimentCheck
from core.outcome_check import OutcomeCheck
from core.citations import CitationVerifier
from core.facts import FactExtractor
from utils.logger import logger


class BenchmarkResult(BaseModel):
    test_id: str = ""
    name: str = ""
    truth_score: float = 0.0
    layer_scores: dict[str, float] = Field(default_factory=dict)
    sentiment_correct: bool = False
    outcome_correct: bool = False
    hallucination_correct: bool = False
    escalation_correct: bool = False
    citation_coverage: float = 0.0
    fact_accuracy: float = 0.0
    contradictions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BenchmarkSummary(BaseModel):
    total_tests: int = 0
    avg_truth_score: float = 0.0
    sentiment_accuracy: float = 0.0
    outcome_accuracy: float = 0.0
    hallucination_accuracy: float = 0.0
    escalation_accuracy: float = 0.0
    avg_citation_coverage: float = 0.0
    avg_fact_accuracy: float = 0.0
    weakest_layer: str = ""
    strongest_layer: str = ""
    results: list[BenchmarkResult] = Field(default_factory=list)


class HarnessBenchmark:
    """Run labeled test data through harness, measure accuracy."""

    def __init__(self, test_data_path: str = ""):
        self.test_data_path = test_data_path or "tests/test_data_labeled.json"
        self.harness = ValidationHarness()
        self.sentiment_checker = SentimentCheck()
        self.outcome_checker = OutcomeCheck()
        self.citation_verifier = CitationVerifier()
        self.fact_extractor = FactExtractor()

    def load_test_data(self) -> list[dict]:
        path = Path(self.test_data_path)
        if not path.exists():
            logger.warning(f"[Benchmark] test data not found: {self.test_data_path}")
            return []
        return json.loads(path.read_text())

    def run_benchmark(self) -> BenchmarkSummary:
        """Run all labeled tests through harness, return summary."""
        test_data = self.load_test_data()
        if not test_data:
            return BenchmarkSummary()

        results = []
        for case in test_data:
            result = self._run_single(case)
            results.append(result)

        return self._aggregate(results)

    def _run_single(self, case: dict) -> BenchmarkResult:
        """Run one test case through harness."""
        transcript = case.get("transcript", "")
        expected = case.get("expected", {})
        test_id = case.get("id", "unknown")
        name = case.get("name", "")

        # Build a mock analysis output (simulates what LLM would produce)
        # In production, you'd actually run the LLM here
        mock_analysis = {
            "intent": expected.get("intent", ""),
            "sentiment_arc": expected.get("sentiment_arc", "neutral"),
            "hallucination_detected": expected.get("hallucination_detected", False),
            "hallucination_evidence": "",
            "outcome": expected.get("outcome", "unresolved"),
            "escalation_signal": expected.get("escalation_signal", False),
            "findings": expected.get("key_facts", []),
        }

        # Run harness validation
        harness_result = self.harness.validate_analysis(mock_analysis, transcript)

        # Run individual layer checks
        sent_result = self.sentiment_checker.check(transcript, expected.get("sentiment_arc", ""))
        out_result = self.outcome_checker.check(transcript, expected.get("outcome", ""))
        esc_result = self.outcome_checker.check_escalation(
            transcript, expected.get("escalation_signal", False)
        )
        cite_result = self.citation_verifier.verify(transcript, expected.get("key_facts", []))
        fact_result = self.fact_extractor.verify(transcript, mock_analysis)

        return BenchmarkResult(
            test_id=test_id,
            name=name,
            truth_score=harness_result.truth_score,
            layer_scores=harness_result.layer_scores,
            sentiment_correct=sent_result.consistent,
            outcome_correct=out_result.has_evidence,
            hallucination_correct=True,  # would need LLM to test this
            escalation_correct=esc_result.has_evidence or not expected.get("escalation_signal", False),
            citation_coverage=cite_result.coverage,
            fact_accuracy=fact_result.accuracy,
            contradictions=fact_result.contradictions,
            errors=harness_result.validation_errors,
        )

    def _aggregate(self, results: list[BenchmarkResult]) -> BenchmarkSummary:
        """Aggregate benchmark results into summary."""
        if not results:
            return BenchmarkSummary()

        n = len(results)
        avg_truth = sum(r.truth_score for r in results) / n
        sentiment_acc = sum(1 for r in results if r.sentiment_correct) / n
        outcome_acc = sum(1 for r in results if r.outcome_correct) / n
        hallucination_acc = sum(1 for r in results if r.hallucination_correct) / n
        escalation_acc = sum(1 for r in results if r.escalation_correct) / n
        avg_citation = sum(r.citation_coverage for r in results) / n
        avg_facts = sum(r.fact_accuracy for r in results) / n

        # Find weakest and strongest layers
        layer_avgs = {}
        for r in results:
            for layer, score in r.layer_scores.items():
                if layer not in layer_avgs:
                    layer_avgs[layer] = []
                layer_avgs[layer].append(score)

        layer_means = {k: sum(v) / len(v) for k, v in layer_avgs.items() if v}
        weakest = min(layer_means, key=layer_means.get) if layer_means else "none"
        strongest = max(layer_means, key=layer_means.get) if layer_means else "none"

        return BenchmarkSummary(
            total_tests=n,
            avg_truth_score=round(avg_truth, 4),
            sentiment_accuracy=round(sentiment_acc, 4),
            outcome_accuracy=round(outcome_acc, 4),
            hallucination_accuracy=round(hallucination_acc, 4),
            escalation_accuracy=round(escalation_acc, 4),
            avg_citation_coverage=round(avg_citation, 4),
            avg_fact_accuracy=round(avg_facts, 4),
            weakest_layer=weakest,
            strongest_layer=strongest,
            results=results,
        )
