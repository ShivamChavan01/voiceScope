# Evaluation scoring contract

Contract version: `heuristic_consistency_v2`.

## Scores

| Field | Range | Meaning |
| --- | --- | --- |
| `harness.truth_score` | finite 0–1 | Weighted mean of applicable heuristic layer scores |
| `harness.layer_scores.*` | finite 0–1 | One evaluation check; invalid inputs raise an error |
| `report.quality_score` | integer 0–100 | Uncalibrated LLM quality judgment; invalid values fail report generation |
| `harness.fact_check_status` | `assessed` or `not_assessed` | Whether the evaluation contains comparable numeric findings |
| `harness.validation_passed` | boolean | True only when no validation errors exist |

The historical field name `truth_score` is retained for API compatibility. It does not mean probability of truth. The confidence label is a threshold band on this heuristic score, not calibrated confidence. Scores are never silently capped because a call has an escalation or model flag.

The numeric layer evaluates distinct numeric values in analysis `findings`. Its numerator is the count of values found in the transcript; its denominator is the count of distinct claimed values. Currency is part of the value. Metadata, policy excerpts, quality scores, and duration are excluded. Numeric formatting such as `$1,000.00` and `$1000` normalizes to the same value.

Leading numeric signs are part of the value: `-100` does not support a claim of `100`. Unicode minus and either dollar/sign order normalize consistently. Date/identifier hyphens remain separators. Numeric support still does not establish complete semantic correctness or prove a voice-agent hallucination.

An absent value becomes an unsupported **analysis claim**. It does not establish a voice-agent hallucination. If the transcript or numeric claims are absent, the fact layer is omitted from the weighted mean and marked `not_assessed`. No-claim calls receive no perfect fact layer as a substitute for evidence.

## Failure states

| `status` | `evaluation_status` | Trigger |
| --- | --- | --- |
| `failed` | `failed` | Transcription, analysis, or report stage did not complete |
| `partial` | `needs_review` | Stages completed, but pipeline errors or validation errors remain |
| `completed` | `validated` | Stages completed and checks produced no errors |

Audio precheck failures currently return `status=failed` before analysis. Schema failure stops downstream heuristics. A report is not generated after analysis fails. Failed and partial evaluations are excluded from real-call flag-rate denominators.

`validated` means the implemented checks passed, not that a transaction succeeded or every company policy was followed. A false model flag appears as **Not flagged · unverified**. Missing evidence never means **Clean**. New persisted results retain the full transcript, model analysis, report, errors, and checks in `evaluation`. Historical rows retain their original limits.

## Finding categories

The intended evidence contract distinguishes the following categories. The existing LLM boolean does not yet implement this full contract and must not be presented as a confirmed violation detector.

| Category | Required interpretation |
| --- | --- |
| Hallucination | A factual assertion contradicts an authoritative source tied to the same subject and time |
| Policy violation | An observed action or promise contradicts a configured policy |
| Unverified claim | A claim lacks corroborating evidence; for example, a claimed refund without a recorded tool result |
| Insufficient evidence | Input, source, or tool records are missing or inconclusive |

A confirmed finding needs the exact claim, source location, applicable policy and version, evidence, severity, and explanation. Missing tool logs cannot be promoted to a failed transaction. A failed refund result tied to the claimed action can support a contradiction; absence of the result cannot.

A fact-layer failure describes the evaluator's analysis. It must not be worded as proof that the voice agent contradicted the transcript.

## Benchmark interpretation

The packaged fixture checks offline heuristic consistency against labels. It does not independently predict hallucinations. `hallucination_accuracy=null` and `hallucination_evaluated=0` mean that metric was not measured. A case with an explicit independent `analysis` prediction can be compared against its expected boolean. Do not compare consistency scores with product detection accuracy.

## Structured policy assessment

The separate `evaluation.reliability` version `1` contract now implements bounded policy findings, unverified refund-completion claims, and insufficient-evidence states. See [supported rules and evidence requirements](reliability.md). These findings are independent of legacy heuristic scores and model flags. `deterministic_checks_completed` identifies synthetic scenarios evaluated without an LLM; it does not claim a successful model evaluation. Confirmed policy matches require explicit transcript roles and an applied policy snapshot. Inferred roles require review.


## Independent policy benchmark

The separate `policy_detector_labeled` benchmark calls the production detector using transcript and policy inputs, then compares its findings with manually authored labels. Category, certainty, severity, policy type, evidence turn indices, and missing-evidence requirements must match within the same case. All challenge cases remain in the overall denominator. It does not measure general hallucinations. See [dataset, metrics, and known misses](policy-benchmark.md).
