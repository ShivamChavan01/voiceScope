# Release-blocker fixes — October 31, 2026

The reproduced application defects from [FINAL_QA_REPORT.md](FINAL_QA_REPORT.md) are fixed locally and covered by regression tests. This follow-up records the new artifact; the original QA report remains the historical evidence of the failures. No commit, push, merge, deployment, production configuration change, or credential change was performed.

## Changes and verification

| QA finding | Fix | Regression evidence |
| --- | --- | --- |
| F01: same-origin IPv4 requests and fonts rejected | Recover the actual loopback Host only when Next has normalized the URL to localhost; restrict recovery to explicit loopback authorities on the same port. Keep exact origin checks, TLS rules, authentication and cross-site rejection. Invalid ports fail closed. | Real NextRequest tests cover IPv4, IPv6, localhost, cross-alias/port/attacker origins and malformed Host. The production browser now asserts actual font responses and creates/removes a synthetic policy using browser fetch. |
| F02: financial transfer misclassified as refusing escalation | Match caller/human-targeted refusal grammar. Skip unrelated objects, including “transfer you money”; inspect subsequent refusals so an unrelated earlier clause cannot hide an actual supervisor refusal. | Existing cases plus financial-object, multiple-refusal, alternative-offer and explicit-human-target cases pass. Persisted synthetic UI has no false policy finding. |
| F03: signed amount invisible to STT comparison | Preserve leading signs, including Unicode minus and either currency/sign order. Detect written numeric-sign differences as amount discrepancies. Keep date/identifier hyphens separate. | Automatic and synthetic human-reference tests cover signed amounts and decimals. Browser displays **20.0% estimated disagreement**, one amount discrepancy, and **Needs human review** for the synthetic `100` versus `-100` case. This is not a real-call accuracy metric. |
| F04: opposite signs receive perfect numeric support | Preserve signed Decimal values and currency presence when comparing distinct numeric claims. | Opposite signs fail support; Unicode-minus and currency formatting equivalents match; identifier separators are not negative signs. No score clamping. |
| F05: unrelated negation hides an affirmative guarantee | Apply negation checks through the matched promise rather than treating a later contrasting time as negating it. Preserve sentence-wide safeguards for reported, quoted, hypothetical and example statements. | Positive promises followed by “not tomorrow/next week” are detected; actual negations and reported/example suffixes remain unconfirmed. |
| F06: saved private source echoed in reference errors | Replace raw ValueError/Pydantic text with a fixed actionable error. | Malformed saved-source canary no longer appears in authenticated 422 output. |
| F07: raw startup exception enters logs | Log the database operation and exception type instead of its message. | Captured private logging sinks omit the synthetic secret-shaped canary. |
| F08: retired reference knowledge remains indexed | Upsert current chunks first, then delete obsolete IDs. Empty sources clear the collection and disable queries. Failed upserts retain the previous index while marking it unavailable. | Real embedded Chroma tests cover shrinking, clearing, re-enabling, and failed upserts using deterministic local embeddings. |
| F09: installer advisories omitted by requirements audit | Pin **pip 26.2.2** and **setuptools 84.1.0** in both Docker stages. Add complete installed-image inventory auditing to CI through the existing strict advisory assessment. | Raw final-image audit reports no pip/setuptools findings; only the existing Chroma records remain. CLI tests verify inventory flags and rejection of unknown advisories. |

An additional STT cache regression prevents older scored results/findings from continuing to appear as current after the signed-number correction. New comparisons carry `comparison_version=signed_numbers_v2`. Older scored reviews are shown unscored with an explicit request to compare again. Cached audio, the reference, annotations and expiry remain intact; reading does not submit to Deepgram or extend retention. Existing unscored real-call evidence keeps its missing-evidence explanations. Historical primary analysis/policy reports are snapshots and are not silently re-evaluated through a paid provider.

## Files changed by the fixes

Implementation: `frontend/src/lib/operator-auth.ts`, `core/reliability.py`, `core/stt_quality.py`, `core/stt_service.py`, `core/facts.py`, `core/knowledge_base.py`, `api/stt_routes.py`, `main.py`, `tools/dependency_audit.py`.

Release configuration: `Dockerfile`, `.github/workflows/ci.yml`.

Tests: `frontend/tests/operator-auth.test.mjs`, `frontend/tests/private-access.browser.mjs`, `tests/test_reliability.py`, `tests/test_stt_quality.py`, `tests/test_stt_review_api.py`, `tests/test_evaluation_contract.py`, `tests/test_error_privacy.py`, `tests/test_knowledge_refresh.py`, `tests/test_dependency_audit.py`.

Documentation: this file, the follow-up links in `FINAL_QA_REPORT.md` and `RELEASE_READINESS.md`, and the signed-value/cache contracts in `docs/stt-quality.md` and `docs/scoring-contract.md`. Existing unrelated changes were preserved; no existing test was removed or skipped.

## Actual checks

Private evidence is retained under ignored `.gstack/release-fixes/`. Baseline red tests and intermediate failures remain available there; they have not been relabeled as passing.

| Command / check | Result |
| --- | --- |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest -q` | **715 passed**, one Starlette/httpx deprecation warning; `backend-ready.log`, exit 0. |
| `cd frontend && npm test` | **56 passed**, exit 0. |
| `.venv/bin/python -m ruff check .` | Pass, exit 0. |
| `.venv/bin/python -m mypy . --ignore-missing-imports --exclude sdk/` | Pass, 135 source files, exit 0; existing notes about unchecked untyped bodies remain. |
| `cd frontend && npx tsc --noEmit` | Pass, exit 0. |
| `cd frontend && npm run lint` | Pass, exit 0. |
| `npm run build` in the isolated current frontend snapshot | Production build passes, exit 0. |
| `docker build -t voicescope-release-fixes:ready .` | Pass, exit 0. |
| Full pytest, configured mypy and Ruff inside the rebuilt Python 3.11 image | **715 passed**; mypy 134 source files and Ruff pass; combined exit 0. |
| Original independent Python QA reproductions | **8 passed**, exit 0. |
| Final policy regression suite | **84 passed**, including the newly checked reported/example suffixes. |
| Existing private-access, Calls UI and STT browser suites | Pass. Calls UI uses mocked API responses; private-access performs actual authenticated mutations/fonts; STT exercises actual cached authorized audio and seeking. |
| Extended browser against production-mode frontend and actual isolated API/SQLite | All **9 journeys pass**, zero page errors; actual CRUD/reload, corrected findings, upload terminal error, empty state and mobile view. Its one console error is the deliberately injected 503; aborted navigation/prefetch requests are recorded separately. |
| Hostile-access/path/header harness | **59 checks pass**. Legitimate same-origin success is covered separately by real NextRequest and browser tests. |
| Fresh-volume/container replacement/restart, recording expiry and receipt smoke | Pass with the final image. Non-root, writable home, private database modes, terminal missing-provider error, report retention, and receipt persistence verified. |
| Docker context and embedded-Chroma boundary | Pass: 11 private canaries excluded, 3 required fixtures retained; Rust transport forced and no Chroma server routes. |
| Raw complete final-image package audit | Exit **1**, **five Chroma records/four unique IDs**; **zero pip/setuptools findings**. Not a clean raw audit. |
| `python -m tools.dependency_audit --inventory .gstack/release-fixes/image-ready-packages.txt` using the existing isolated audit environment | Exit **0 with the existing explicit, version-bound Chroma exception**; not a vulnerability fix. |
| `python scripts/run_benchmark.py --min-truth 0.7` | Pass, exit 0; heuristic consistency, not measured hallucination accuracy. |
| `python scripts/run_reliability_benchmark.py --json ...` | Exit **1**: unchanged **25/28** exact cases, supported 24/24, challenge 1/4. No thresholds or labels were weakened. |
| `git diff --check` | Pass. No files staged. |

Container test invocation installs test tools into `/tmp/devtools`, mounts the repository tests read-only, and runs `python -m pytest -q && python -m mypy . --ignore-missing-imports --exclude sdk/ && python -m ruff check .` with `PYTHON_DOTENV_DISABLED=1`, empty `DATABASE_URL`, and `PYTHONPATH=/tmp/devtools:/app`.

### Test-harness corrections

An early isolated launcher resolved `.venv/bin/python` to its system interpreter. That interpreter loaded ancestor dotenv configuration, invalidating the claimed absent-provider setup. A synthetic empty-audio test reached the already authorized Deepgram provider and failed; no real recording was submitted by that upload. The launcher was corrected to preserve the virtualenv executable path. The final backend's provider state was independently checked as **Deepgram unconfigured**, and actual upload failure, browser, and cache checks were rerun. No credentials were printed or changed.

An intermediate container image was older than two newly added reported-suffix tests and failed them. The corrected, frozen final image passes all 715 tests. An early browser selector also matched both the new discrepancy evidence and full reference transcript; it was scoped to the evidence article, retaining the content assertion. These intermediate failures remain recorded and are not final-image results.

## Real-call and release limits

- The existing authorized real call still plays, seeks to independent-reference timestamps, and reloads with its cached reference: **20 original turns, 39 independent segments, zero new browser reference submissions**. It correctly remains **Not scored** because trustworthy Bolna utterance timing and speaker identity are missing.
- Fresh Bolna execution/recording retrieval was verified in the independent QA pass; the recording downloader was not changed by these fixes. A fresh Deepgram transcription, fresh Bolna-originated webhook delivery, scored real-call WER, and new provider-backed full analysis were not re-established here.
- The detector remains a bounded English-pattern implementation. The three packaged challenge misses (`challenge-assure`, `challenge-lead`, `challenge-returned`) are still visible. This work fixes the reproduced correctness regressions; it does not establish general production precision/recall.
- Raw npm advisories remain **19 moderate and 2 low** from the preceding audit; the frontend dependency graph was not changed by these fixes. ChromaDB remains **1.5.9**, with the narrowly assessed embedded-only exception valid only **before November 7, 2026 UTC**. No new waiver was added.
- Completed-receipt deduplication is still at-least-once processing, not exactly-once provider work across crashes. Independent replica filesystems cannot coordinate.
- The branch remains uncommitted at HEAD `299666b7df94bacbd046f9e06b3e68c9b15d128b`. Local results do not make the old GitHub run green. Exact-commit CI, hosted operator configuration, backend/volume verification, and an approved backup/rollback procedure remain prerequisites before merge/deployment. No production-readiness approval is asserted.

The final image is `voicescope-release-fixes:ready`, ID `sha256:32fead047820d24027eb4f2166d6a222da9f2a1f8a116f791dac1be26392a82f`. The precise source fingerprint and frontend build ID are recorded in `.gstack/release-fixes/verified-artifact.json`; source fixes and tests remain reviewable in the working tree.
