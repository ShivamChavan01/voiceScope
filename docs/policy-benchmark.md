# Policy detector benchmark

The policy benchmark calls the same `evaluate_reliability` function used for real calls. It supplies attributed transcript turns and explicit company policies. Expected findings are loaded separately and are never passed to the detector.

## Run

```bash
.venv/bin/python scripts/run_reliability_benchmark.py --json /tmp/policy-benchmark.json
```

The default gate requires every case to match. The current dataset deliberately includes broader paraphrases that the bounded detector misses, so the default command exits **1** and writes the mismatches. That is an evaluation failure, not a broken runner. Do not lower the threshold to claim improved detection. A configurable `--min-case-accuracy` exists for explicitly chosen experiments; it accepts only finite values from 0 to 1.

Open **Benchmark** in the frontend or call authenticated `GET /api/v1/loop/benchmark/reliability`. Re-running performs a read-only evaluation. It does not change optimizer weights, company policies, prompts, or call records.

## Current dataset

`core/data/reliability_cases.json` version 2 contains 28 manually labeled synthetic cases: 24 supported-pattern regressions and four challenge paraphrases. At introduction, exact matches were **25/28**, comprising **24/24** supported cases and **1/4** challenges. Ten findings matched, none were unexpected, and three were missed. This is a small development regression set, not a held-out test or an estimate of production accuracy.

The visible misses are assurance wording for same-day refund arrival, a refused request for a team lead, and “money returned to your card” as an unverified completion claim. These remain detector coverage gaps. The broader semantic detector has not been implemented.

The input fixtures include compliant conversations, explicit promises and refusals, negation, quoted speech, unrelated refusals, administrative refund steps, conditional approval, caller statements, missing policies, missing transcripts, inferred/unknown roles, multiple findings, and paraphrases. Editing an expected label changes agreement without changing the detector's prediction; regression tests enforce this separation.

## Metrics

- **Exact case match** requires the expected assessment status, all expected findings, no unexpected findings, and valid source evidence.
- **Finding precision** is correct finding labels divided by all predicted findings.
- **Finding recall** is correct finding labels divided by all expected findings.
- **F1** is the harmonic combination derived from true positives, false positives, and false negatives.
- No positive predictions makes precision unavailable. No expected positive labels makes recall unavailable. Empty denominators never become a perfect score.

A finding label includes category, certainty, policy kind, severity, source turn indices, and missing-evidence requirements. Matching is confined to the same case and preserves duplicate counts. A finding from another call cannot compensate for a missed finding. Exact quote and speaker provenance integrity are checked separately and invalidate case success. This source check does not measure whether every explanation is semantically correct.

Results show the source transcript, policy, expected and detected findings, and mismatches. The artifact includes dataset version and SHA-256 so a reported number can be tied to its inputs. Supported and challenge cases both count in the overall denominator.

## Legacy harness

The older `scripts/run_benchmark.py` and `/api/v1/loop/benchmark` remain available for compatibility. They measure evaluator consistency with supplied fixture answers. They do not independently measure general hallucination detection. The frontend keeps them under **Legacy harness consistency checks** and removes the disconnected “improvement loop,” weight tuning, and prompt suggestions from this page. The legacy backend optimizer endpoints remain available but are not evidence of improved production behavior.

No live LLM, transcription provider, payment tool, or Bolna call is exercised by this benchmark. Real-call replay is documented separately in [Bolna verification](bolna-verification.md).

## Case relevance

Each case supplies only the fictional rule it tests. Refund-promise cases use the refund rule; supervisor-transfer cases use the escalation rule. Refund-action evidence cases supply no company rule and test unverified claims directly. The generic order-tracking example has been replaced by a refund estimate without a guarantee. Each case includes a human-authored purpose that is displayed alongside its synthetic conversation and is never passed to the detector. These fixture results are separate from saved real calls.
