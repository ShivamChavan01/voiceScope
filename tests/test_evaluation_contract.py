"""Deterministic regression cases; no paid services or model judgments."""
import pytest

from pydantic import ValidationError

from core.benchmark import HarnessBenchmark
from core.harness import ReportOutput, ValidationHarness
from core.facts import FactExtractor


@pytest.mark.parametrize(('transcript', 'findings', 'expected'), [
    ('Agent: Refund $50 in 5 days for order 123.', ['Refund $50', '5 days', 'order 123'], 1.0),
    ('Agent: Refund $50 in 5 days.', ['Refund $75', '5 days'], 0.5),
    ('Agent: Refund $50.', ['Refund $75', '7 days', 'order 999'], 0.0),
    ('Agent: Refund $1,000.00.', ['Refund $1000'], 1.0),
    ('Agent: Order 50.', ['Refund $50'], 0.0),
    ('Agent: Refund $50.', ['Refund $75', 'Refund $75'], 0.0),
])
def test_numeric_support_is_per_distinct_analysis_claim(transcript, findings, expected):
    result = FactExtractor().verify(transcript, {'findings': findings})
    assert result.status == 'assessed'
    assert result.accuracy == expected
    assert result.contradictions == []
    assert len(result.unsupported_claims) <= result.claims_checked


@pytest.mark.parametrize(('transcript', 'analysis'), [
    ('', {'findings': ['Refund $50']}),
    ('Hello', {}),
    ('Refund $50', {'quality_score': 90, 'policy_evidence': 'Refunds over $100'}),
    ('Refund $50', {'findings': None}),
])
def test_no_comparable_claims_is_explicitly_not_assessed(transcript, analysis):
    result = FactExtractor().verify(transcript, analysis)
    assert result.status == 'not_assessed'
    assert result.claims_checked == 0



@pytest.mark.parametrize('score', [-1, 101, float('nan'), float('inf')])
def test_report_rejects_invalid_quality_score(score):
    with pytest.raises(ValidationError):
        ReportOutput(quality_score=score)


@pytest.mark.parametrize('score', [0, 100])
def test_report_accepts_score_boundaries(score):
    assert ReportOutput(quality_score=score).quality_score == score


@pytest.mark.parametrize('score', [-0.1, 1.1, float('nan'), float('inf')])
def test_weighted_score_rejects_invalid_layer_instead_of_clamping(score):
    with pytest.raises(ValueError, match='expected finite'):
        ValidationHarness()._compute_truth_score({'facts': score})


def test_unsupported_finding_fails_validation_without_accusing_call_agent():
    result = ValidationHarness().validate_analysis({
        'intent': 'refund', 'sentiment_arc': 'neutral', 'outcome': 'unresolved',
        'hallucination_detected': False, 'escalation_signal': False, 'findings': ['Refund $75'],
    }, 'Agent: Your refund is $50. The issue is still unresolved.')
    assert not result.validation_passed
    assert result.validated_output == {}
    assert result.fact_check_status == 'assessed'
    assert result.layer_scores['facts'] == 0
    assert any('analysis numeric claim' in error for error in result.validation_errors)


def test_no_numeric_findings_does_not_add_perfect_fact_layer():
    result = ValidationHarness().validate_analysis({'intent': 'greeting'}, 'Hello')
    assert result.fact_check_status == 'not_assessed'
    assert 'facts' not in result.layer_scores



def test_offline_benchmark_does_not_fabricate_hallucination_accuracy(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    summary = HarnessBenchmark().run_benchmark()
    assert summary.total_tests == 10
    assert summary.hallucination_accuracy is None
    assert summary.hallucination_evaluated == 0
    assert summary.benchmark_kind == 'offline_harness_consistency'


def test_missing_benchmark_fails_explicitly(tmp_path):
    with pytest.raises(FileNotFoundError):
        HarnessBenchmark(str(tmp_path / 'missing.json')).run_benchmark()


def test_independent_benchmark_prediction_can_fail():
    result = HarnessBenchmark()._run_single({
        'id': 'wrong-prediction', 'transcript': 'Agent: Hello.',
        'expected': {'hallucination_detected': True},
        'analysis': {'hallucination_detected': False},
    })
    assert result.hallucination_correct is False


def test_invalid_schema_returns_failure_before_heuristics_can_crash():
    result = ValidationHarness().validate_analysis({
        'intent': 'refund', 'sentiment_arc': 'neutral', 'outcome': 'unresolved',
        'hallucination_detected': True, 'escalation_signal': False,
        'quality_score': 'not a score', 'findings': [None],
    }, 'Agent: Hello.')
    assert not result.validation_passed
    assert result.truth_score == 0
    assert result.layer_scores == {'schema': 0}


def test_conflicting_boolean_and_evidence_fails_cross_check():
    from core.cross_check import CrossChecker

    result = CrossChecker().check({
        'hallucination_detected': False,
        'hallucination_evidence': 'Agent promised free shipping contrary to policy.',
    })
    assert not result.consistent


def test_same_analysis_on_different_transcripts_is_not_duplicate():
    harness = ValidationHarness()
    analysis = {
        'intent': 'greeting', 'sentiment_arc': 'neutral', 'outcome': 'unresolved',
        'hallucination_detected': False, 'escalation_signal': False,
    }
    harness.validate_analysis(analysis, 'Customer: Hello.')
    result = harness.validate_analysis(analysis, 'Customer: Hi there.')
    assert result.layer_scores['duplicate'] == 1


def test_repeated_benchmark_is_reproducible():
    benchmark = HarnessBenchmark()
    assert benchmark.run_benchmark() == benchmark.run_benchmark()


def test_benchmark_cli_emits_unmeasured_instead_of_fake_accuracy(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    artifact = tmp_path / 'benchmark.json'
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'run_benchmark.py'
    result = subprocess.run(
        [sys.executable, str(script), '--json', str(artifact)],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert 'not measured (no independent predictions)' in result.stdout
    assert json.loads(artifact.read_text())['hallucination_accuracy'] is None
