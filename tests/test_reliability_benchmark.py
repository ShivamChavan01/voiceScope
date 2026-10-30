import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.reliability_benchmark import run_reliability_benchmark
from core.reliability import ReliabilityReport

FIXTURE = Path(__file__).resolve().parents[1] / 'core/data/reliability_cases.json'


def write_fixture(tmp_path, change):
    data = json.loads(FIXTURE.read_text())
    change(data)
    path = tmp_path / 'fixture.json'
    path.write_text(json.dumps(data))
    return path


def test_production_predictions_are_reproducible_and_challenges_are_not_hidden():
    result = run_reliability_benchmark()
    assert result == run_reliability_benchmark()
    assert result.total_cases == 28
    assert result.supported_cases == 24
    assert result.supported_passed == 24
    assert result.challenge_cases == 4
    assert result.challenge_passed < 4
    assert result.passed_cases < result.total_cases
    assert result.metrics.false_negatives > 0
    assert len(result.dataset_sha256) == 64
    assert not any(case.evidence_errors for case in result.results)


def test_expected_labels_do_not_become_predictions(tmp_path):
    baseline = run_reliability_benchmark()
    path = write_fixture(tmp_path, lambda data: data['cases'][2].update(expected=[]))
    result = run_reliability_benchmark(path)
    assert result.results[2].actual == baseline.results[2].actual
    assert result.results[2].passed is False
    assert result.metrics.false_positives == baseline.metrics.false_positives + 1
    assert result.dataset_sha256 != baseline.dataset_sha256


def test_bad_detector_cannot_pass_using_expected_labels(monkeypatch):
    monkeypatch.setattr('core.reliability_benchmark.evaluate_reliability', lambda turns, policies: ReliabilityReport(status='assessed'))
    result = run_reliability_benchmark()
    assert result.metrics.true_positives == 0
    assert result.metrics.false_negatives > 0
    assert result.metrics.precision is None
    assert result.metrics.recall == 0
    assert result.metrics.f1 == 0


def test_spurious_duplicate_findings_are_counted(monkeypatch):
    from core.reliability import evaluate_reliability

    def duplicate(turns, policies):
        report = evaluate_reliability(turns, policies)
        report.findings = report.findings + report.findings
        return report

    monkeypatch.setattr('core.reliability_benchmark.evaluate_reliability', duplicate)
    result = run_reliability_benchmark()
    assert result.metrics.false_positives > 0
    assert result.metrics.precision < 1


def test_fabricated_quote_cannot_pass_even_with_matching_classification(monkeypatch):
    from core.reliability import evaluate_reliability

    def fabricate(turns, policies):
        report = evaluate_reliability(turns, policies)
        for finding in report.findings:
            for evidence in finding.evidence:
                evidence.quote = 'fabricated quote'
        return report

    monkeypatch.setattr('core.reliability_benchmark.evaluate_reliability', fabricate)
    result = run_reliability_benchmark()
    assert result.results[2].evidence_errors
    assert not result.results[2].passed


@pytest.mark.parametrize('index', [-1, 100])
def test_invalid_fixture_evidence_is_rejected(tmp_path, index):
    path = write_fixture(tmp_path, lambda data: data['cases'][2]['expected'][0].update(turn_indices=[index]))
    with pytest.raises(ValidationError):
        run_reliability_benchmark(path)


@pytest.mark.parametrize('mutate', [
    lambda data: data.update(cases=[]),
    lambda data: data['cases'].append(data['cases'][0]),
    lambda data: data['cases'][0].update(policies=['missing']),
    lambda data: data['cases'][0].update(analysis={'hallucination_detected': False}),
])
def test_invalid_datasets_fail_explicitly(tmp_path, mutate):
    with pytest.raises(ValidationError):
        run_reliability_benchmark(write_fixture(tmp_path, mutate))


def test_missing_dataset_is_not_a_successful_zero(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_reliability_benchmark(tmp_path / 'missing.json')


def test_no_positive_labels_or_predictions_have_unmeasured_rates(tmp_path):
    path = write_fixture(tmp_path, lambda data: data.update(cases=data['cases'][:1]))
    result = run_reliability_benchmark(path)
    assert result.passed_cases == 1
    assert result.metrics.precision is None
    assert result.metrics.recall is None
    assert result.metrics.f1 is None


def test_api_returns_actual_predictions_and_mismatches(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    import middleware.auth

    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'benchmark-test'}))
    response = TestClient(app).get('/api/v1/loop/benchmark/reliability', headers={'X-API-Key': 'benchmark-test'})
    assert response.status_code == 200
    assert response.json() == run_reliability_benchmark().model_dump(mode='json')
    assert response.json()['passed_cases'] < response.json()['total_cases']
    monkeypatch.setattr('core.reliability_benchmark.run_reliability_benchmark', lambda: (_ for _ in ()).throw(FileNotFoundError()))
    failed = TestClient(app).get('/api/v1/loop/benchmark/reliability', headers={'X-API-Key': 'benchmark-test'})
    assert failed.status_code == 503


def test_api_requires_auth(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    import middleware.auth

    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'benchmark-test'}))
    assert TestClient(app).get('/api/v1/loop/benchmark/reliability').status_code == 401


def test_cli_reports_challenge_failures_and_writes_artifact(tmp_path):
    import subprocess
    import sys

    script = FIXTURE.parents[2] / 'scripts/run_reliability_benchmark.py'
    artifact = tmp_path / 'result.json'
    process = subprocess.run([sys.executable, str(script), '--json', str(artifact)], capture_output=True, text=True)
    assert process.returncode == 1
    assert 'MISMATCH: challenge-' in process.stdout
    assert 'FAIL' in process.stdout
    assert json.loads(artifact.read_text())['metrics']['false_negatives'] > 0
    passing = write_fixture(tmp_path, lambda data: data.update(cases=data['cases'][:1]))
    process = subprocess.run([sys.executable, str(script), '--dataset', str(passing)], capture_output=True, text=True)
    assert process.returncode == 0
    assert '1/1 exact case matches' in process.stdout
    for threshold in ('nan', 'inf', '-0.1', '1.1'):
        process = subprocess.run([sys.executable, str(script), '--min-case-accuracy', threshold], capture_output=True, text=True)
        assert process.returncode == 2


def test_cases_carry_only_rules_relevant_to_the_behavior_under_test():
    results = {case.id: case for case in run_reliability_benchmark().results}
    timing = results['ordinary']
    assert 'refund' in timing.turns[0].text.lower()
    assert [policy.kind for policy in timing.policies] == ['no_same_day_refund_guarantee']
    assert timing.expected == []
    assert timing.passed
    assert all(case.purpose.strip() for case in results.values())
    assert [policy.kind for policy in results['refusal'].policies] == ['honor_escalation_request']
    assert results['refund-done'].policies == []
    assert results['refund-done'].actual[0].category == 'unverified_claim'
    assert all(len(case.policies) <= 1 for case in results.values())


def test_case_purpose_is_required_and_not_sent_to_the_detector(tmp_path, monkeypatch):
    from core.reliability import evaluate_reliability

    received = []

    def record_inputs(turns, policies):
        received.append((turns, policies))
        assert all(set(turn) == {'speaker', 'role', 'role_source', 'text'} for turn in turns)
        return evaluate_reliability(turns, policies)

    monkeypatch.setattr('core.reliability_benchmark.evaluate_reliability', record_inputs)
    result = run_reliability_benchmark()
    assert len(received) == result.total_cases
    with pytest.raises(ValidationError):
        run_reliability_benchmark(write_fixture(tmp_path, lambda data: data['cases'][0].update(purpose='')))
