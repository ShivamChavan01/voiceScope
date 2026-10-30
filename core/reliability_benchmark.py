"""Run the production policy detector against separately authored expected findings."""

import hashlib
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.reliability import PolicyRule, evaluate_reliability


class Turn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    speaker: int = Field(ge=0)
    role: Literal['agent', 'customer', 'unknown']
    role_source: Literal['transcript_label', 'model_inference', 'unknown']
    text: str


class FindingLabel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    category: Literal['policy_violation', 'unverified_claim', 'insufficient_evidence']
    status: Literal['confirmed', 'needs_review']
    policy_kind: Literal['no_same_day_refund_guarantee', 'honor_escalation_request'] | None
    severity: Literal['high', 'medium', 'info']
    turn_indices: tuple[int, ...]
    missing_evidence: tuple[str, ...] = ()

    def key(self) -> str:
        return self.model_dump_json()


class LabeledCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    scope: Literal['supported_patterns', 'challenge_paraphrases']
    policies: list[str]
    turns: list[Turn]
    expected_status: Literal['assessed', 'insufficient_evidence']
    expected: list[FindingLabel]


class Dataset(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal['2']
    policies: list[PolicyRule]
    cases: list[LabeledCase] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_references(self):
        ids = {policy.id for policy in self.policies}
        if len(ids) != len(self.policies) or len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError('Benchmark IDs must be unique')
        for case in self.cases:
            if len(set(case.policies)) != len(case.policies) or not set(case.policies) <= ids:
                raise ValueError('Unknown or duplicate policy reference')
            for label in case.expected:
                if any(index < 0 or index >= len(case.turns) for index in label.turn_indices):
                    raise ValueError('Expected evidence index is outside the transcript')
        return self


class DetectionMetrics(BaseModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None


class CaseResult(BaseModel):
    id: str
    name: str
    purpose: str
    scope: str
    passed: bool
    turns: list[Turn]
    policies: list[PolicyRule]
    expected_status: str
    actual_status: str
    expected: list[FindingLabel]
    actual: list[FindingLabel]
    evidence_errors: list[str]


class ReliabilityBenchmarkResult(BaseModel):
    benchmark_kind: Literal['policy_detector_labeled'] = 'policy_detector_labeled'
    dataset_version: str
    dataset_sha256: str
    data_source: Literal['synthetic_hand_labeled'] = 'synthetic_hand_labeled'
    total_cases: int
    passed_cases: int
    exact_case_accuracy: float
    supported_cases: int
    supported_passed: int
    challenge_cases: int
    challenge_passed: int
    metrics: DetectionMetrics
    by_category: dict[str, DetectionMetrics]
    results: list[CaseResult]
    limitations: list[str] = Field(default_factory=lambda: [
        'Small synthetic regression set authored for this detector; not a held-out production evaluation.',
        'Challenge paraphrases are included in overall results and may exceed supported pattern coverage.',
        'Measures transcript policy findings, not general hallucination detection, STT accuracy, or external actions.',
        'Exact matches require category, certainty, policy type, severity, evidence turns, and missing-evidence labels.',
    ])


def _metrics(expected: Counter, actual: Counter) -> DetectionMetrics:
    tp = sum((expected & actual).values())
    fp = sum((actual - expected).values())
    fn = sum((expected - actual).values())
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return DetectionMetrics(
        true_positives=tp, false_positives=fp, false_negatives=fn,
        precision=precision, recall=recall,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    )


def run_reliability_benchmark(path: str | Path | None = None) -> ReliabilityBenchmarkResult:
    fixture = Path(path) if path is not None else Path(__file__).parent / 'data' / 'reliability_cases.json'
    raw = fixture.read_bytes()
    dataset = Dataset.model_validate_json(raw)
    policies = {policy.id: policy for policy in dataset.policies}
    results = []
    for case in dataset.cases:
        turns = [turn.model_dump() for turn in case.turns]
        # The detector receives input only. Expected labels are compared after prediction.
        prediction = evaluate_reliability(turns, [policies[key] for key in case.policies])
        snapshots = {policy.id: policy.kind for policy in prediction.policy_snapshots}
        actual = []
        errors = []
        for finding in prediction.findings:
            actual.append(FindingLabel(
                category=finding.category, status=finding.status,
                policy_kind=snapshots.get(finding.policy_id) if finding.policy_id is not None else None, severity=finding.severity,
                turn_indices=tuple(item.turn_index for item in finding.evidence),
                missing_evidence=tuple(sorted(finding.missing_evidence)),
            ))
            if finding.policy_id is not None and finding.policy_id not in snapshots:
                errors.append('Finding references a policy absent from the applied snapshots')
            for evidence in finding.evidence:
                if evidence.turn_index >= len(turns):
                    errors.append('Evidence turn is outside the transcript')
                    continue
                turn = turns[evidence.turn_index]
                if (evidence.quote not in turn['text'] or evidence.speaker_role != turn['role']
                        or evidence.role_source != turn['role_source']):
                    errors.append('Evidence quote or speaker attribution does not match its source turn')
        expected_counts = Counter(label.key() for label in case.expected)
        actual_counts = Counter(label.key() for label in actual)
        results.append(CaseResult(
            id=case.id, name=case.name, purpose=case.purpose, scope=case.scope,
            turns=case.turns, policies=[policies[key] for key in case.policies],
            passed=(expected_counts == actual_counts and prediction.status == case.expected_status and not errors),
            expected_status=case.expected_status, actual_status=prediction.status,
            expected=case.expected, actual=actual, evidence_errors=errors,
        ))
    categories = ['policy_violation', 'unverified_claim', 'insufficient_evidence']
    expected = Counter((case.id, label.key()) for case in results for label in case.expected)
    actual_labels = Counter((case.id, label.key()) for case in results for label in case.actual)
    return ReliabilityBenchmarkResult(
        dataset_version=dataset.version, dataset_sha256=hashlib.sha256(raw).hexdigest(),
        total_cases=len(results), passed_cases=sum(case.passed for case in results),
        exact_case_accuracy=sum(case.passed for case in results) / len(results),
        supported_cases=sum(case.scope == 'supported_patterns' for case in results),
        supported_passed=sum(case.scope == 'supported_patterns' and case.passed for case in results),
        challenge_cases=sum(case.scope == 'challenge_paraphrases' for case in results),
        challenge_passed=sum(case.scope == 'challenge_paraphrases' and case.passed for case in results),
        metrics=_metrics(expected, actual_labels),
        by_category={category: _metrics(
            Counter((case.id, label.key()) for case in results for label in case.expected if label.category == category),
            Counter((case.id, label.key()) for case in results for label in case.actual if label.category == category),
        ) for category in categories}, results=results,
    )
