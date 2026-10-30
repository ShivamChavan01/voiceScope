# VoiceScope repository audit and delivery plan

Audit date: October 25, 2026. Target: a credible working demo before October 31.

## Architecture and implementation inventory

| Area | Implementation | Observation |
| --- | --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind | Overview, Runs with detail drawer, Benchmark, Settings |
| API | FastAPI, Pydantic, Uvicorn | Audio, transcript, SSE, batch, generic webhook, runs, monitoring, QA, knowledge, extraction, feedback, benchmark |
| Agents | Transcription, speaker classification, analysis, report | STT followed by provider-backed LLM calls; retrieval supplies context |
| Evaluation | `core/harness.py`, citations, facts, cross-check, sentiment, outcome | Deterministic heuristics check model output; no independent semantic truth oracle |
| Storage | asyncpg PostgreSQL, SQLite fallback, Chroma | Costs and metrics are separate writes; full evaluation persistence added locally |
| Providers | OpenAI, Anthropic, Gemini, Groq, Ollama, Mistral, OpenRouter, OpenCode | Registry supports fallback providers and circuit breakers |
| STT | Deepgram, Whisper, Gemini | Actual decoding/provider execution needs live credentials and audio |
| Background work | `core/batch.py` uses `asyncio.create_task` and a dictionary | No durable worker, queue, leases, or restart recovery |
| Monitoring | Threshold rules and incidents in `storage/monitoring.py` | Alert checks are API-triggered; no scheduled job was found |
| Other modules | Assertion harness, calibration, feedback, optimizer, prompt tracker, extraction, QA | Some features are heuristic or informational; optimizer weights do not change main scoring |
| Clients | CLI and Python SDK | Independent paths need persistence and compatibility checks before broader claims |
| Deployment | Vercel proxy, Docker, Railway config, Compose, GitHub Actions | Separate frontend/backend; runtime fixtures moved out of excluded tests; policy file explicitly included |

PostgreSQL SSL is hardcoded to `require`; default Compose PostgreSQL may therefore fall back to SQLite. Failures can split data across local files and database storage. Tenant context is absent from most stores. This is not a tenant-isolated product yet.

## Reported inconsistencies and source findings

| Symptom | Root cause or current evidence | Local correction |
| --- | --- | --- |
| Total 0, analyzed 12, Runs 16 | Different populations: time-windowed metrics, history capped at 12, paginated Runs, and independent persistence paths. SSE writes Runs but not call metrics. Re-seeding used to append duplicate metrics. | Overview uses one all-time run summary; real/synthetic and completed denominators are explicit |
| Negative fact accuracy | Every transcript number compared with every analysis number; mismatch pairs divided by fact count | Score distinct supported analysis values once; absent claims are unsupported, no pairwise penalty |
| Clean beside contradictory report | UI trusts boolean independently; harness errors did not consistently fail validation; fact errors attributed to call agent; hidden score caps | Review/failure labels, corrected language, error-driven status, no display cap |
| Benchmark has 0 labeled calls | Runtime fixture under `tests/` excluded by `.dockerignore`; missing file silently returned an empty successful result | Fixture under `core/data`; path relative to module; missing/invalid data fails explicitly |
| Benchmark previously claimed hallucination accuracy | `hallucination_correct=True` hardcoded without independent predictions | Unmeasured metric is null with explicit evaluated count |

The public deployed benchmark endpoint returned zero cases during this audit. Production database records were not inspected, changed, or re-evaluated. Exact causes of individual production count differences remain inferred from source paths, not database-confirmed.

## Bolna webhook audit

`api/schemas.py:parse_bolna_webhook` handles `id`, `agent_id`, `status`, `transcript`, `conversation_duration`, and `telephony_data.recording_url`. This matches the broad shape documented by Bolna's [Get Execution API](https://www.bolna.ai/docs/api-reference/executions/get_execution). Bolna's [webhook guide](https://www.bolna.ai/docs/post-call/polling-call-status-webhooks) documents status updates and custom headers. Configure completion-only events and an authentication header rather than assuming every delivery is a finished call.

At the start of the audit, the handler at `/api/v1/webhooks/call-completed` had these behaviors. Later corrections are recorded below:

- Checks a body-size cap and parses JSON, but lacks a strict Bolna boundary model.
- Rejects intermediate events rather than acknowledging intentional ignored events.
- Requires recording candidates and ignores the supplied transcript.
- Downloads and evaluates synchronously before replying.
- Uses a new random run ID for every retry, without a durable event key.
- Does not persist the execution envelope, agent identity, source timestamps, or tool evidence.
- Logs persistence errors without reliably surfacing failure to the sender.

An existing recording fallback change predates this audit and was preserved. It is not proof of successful live integration.

## Security and reliability blockers

1. The public Next.js proxy injects the backend API key without visitor authentication. This exposes reads, mutations, costly evaluation calls, and deletion routes.
2. Recording URLs are checked before a request, but redirects are followed automatically. Redirect destinations and DNS rebinding need protection. HTTP downloads are buffered before the effective size check.
3. Generic webhook payloads need object/type validation. Durable deduplication, retries, and source authentication are incomplete.
4. Storage writes are separate and exceptions can be swallowed. Failed PostgreSQL connections can silently send writes to instance-local SQLite.
5. Policy and transcript retrieval indexes are shared. There is no reliable tenant isolation. Deleted policy chunks can survive index rebuilding.
6. Request contexts and in-memory state need concurrency review. Batch state and per-process rate limits disappear on restart.
7. Analysis still mixes policy contradictions and hallucinations. LLM-generated report text is not an evidence authority.

Do not expose real customer calls through the current public proxy until access control is fixed. No production secrets or infrastructure were changed during this audit. Local Docker context rules now exclude frontend artifacts and `.env*` files, and explicitly retain the business policy file.

## Prioritized 3–5 day plan

| Order | Work | Acceptance evidence |
| --- | --- | --- |
| Day 1, P0 | Scoring math, explicit failure states, honest benchmark, coherent totals, synthetic labels | Deterministic regressions, full suite, frontend checks; no claims of semantic detection accuracy |
| Day 2, P1 | Dedicated validated Bolna ingestion, custom-header auth, durable unique execution/event key and worker, transcript-first processing | Same event delivered twice yields one run; crash/retry recovers; actual completed Bolna execution persists |
| Day 3, P2 | Versioned company policies, structured findings, exact transcript claims, optional tool evidence | Compliant call, unauthorized claim, missing tool result, failed tool result, and escalation failure have known distinct outcomes |
| Day 4, P3 | Complete call debugging view, three reproducible scenarios, error states, private demo setup | Reload preserves metadata, transcript, policies, tool results, findings, and failure reasons |
| Day 5 | Real call rehearsal and targeted repair | One recorded actual Bolna flow, duplicate delivery proof, current limitations spoken in demo |

The local P0 milestone does not complete the evidence-backed finding taxonomy, durable ingestion, public access control, or live service verification. These remain acceptance gates before the product can be described as reliable.

## End-to-end verification status

| Stage | Current evidence |
| --- | --- |
| Webhook parsing and handler | Unit tests and mocked HTTP tests; live delivery unverified |
| Audio transcription | Provider tests; real audio-to-provider execution unverified in this milestone |
| Analysis and report | Mocked agent and pipeline tests; live model correctness unverified |
| Evaluation | Deterministic scoring and failure-state tests |
| Evidence generation | Legacy model text; verified tool-backed findings not implemented |
| Run persistence | SQLite regression tests, PostgreSQL query mocks; real PostgreSQL end-to-end test pending |
| UI | Unit tests for verdict/score helpers, TypeScript, lint, and build checks; browser flow verification pending |

Record actual verification results in the milestone response. Never infer a working live flow from mocks.

## First local milestone

Changed files are grouped here for review. Pre-existing edits in `api/routes.py`, `core/pipeline.py`, `frontend/src/app/api/[...path]/route.ts`, and `tests/test_api.py` were preserved.

| Change | Files |
| --- | --- |
| Numeric scoring and validation | `core/facts.py`, `core/harness.py`, `core/cross_check.py` |
| Agent boundaries and failure states | `agents/analysis_agent.py`, `agents/report_agent.py`, `core/pipeline.py`, `api/sse.py` |
| Persistent debugging and totals | `storage/db.py`, `storage/monitoring.py`, `api/routes.py` |
| Honest benchmark and demo data | `core/benchmark.py`, `core/data/labeled_calls.json`, `core/demo_seed.py`, `scripts/run_benchmark.py`, `pyproject.toml` |
| UI contracts and labels | `frontend/src/lib/api.ts`, `frontend/src/lib/evaluation.ts`, Overview, Runs, Benchmark, Settings, `frontend/src/components/harness-bar.tsx` |
| Runtime packaging | `.dockerignore` |
| Regression tests | New evaluation-contract, run-summary, API, and frontend helper tests; updated agent, harness, cross-check, pipeline, SSE, webhook, and middleware tests |
| Developer documentation | `README.md`, this audit, `docs/scoring-contract.md`, `docs/demo-walkthrough.md` |

Verified on the final code changes:

- Python suite: **380 passed**, with one existing Starlette/httpx deprecation warning.
- Frontend helper suite: **5 passed**.
- TypeScript, frontend ESLint, production Next.js build, and `git diff --check`: passed.
- Ruff on changed Python files: passed. Repository-wide Ruff still reports existing dotenv/import-order errors in `main.py`.
- Offline benchmark: ten cases loaded; hallucination accuracy explicitly unmeasured. The generated local artifact is `/tmp/voicescope-p0-benchmark.json`.

The test suite originally shared one FastAPI rate-limit budget across test cases. Additional API tests exposed cumulative 429 responses. Tests now reset that budget between cases, and a request-level test confirms rate limiting still blocks within a case. No production rate limits were weakened.

No live Bolna execution, STT/LLM service round trip, real PostgreSQL round trip, browser interaction flow, container build, or production deployment was verified in this milestone. The next live gate needs a completed execution from a designated test agent through secure local configuration.

## Follow-up with existing Bolna calls

The [real-call verification](bolna-verification.md) retrieved the existing agent and four completed calls. Replaying the 72-second execution through local ingestion completed recording download, Deepgram STT, Groq analysis/report, SQLite persistence, and exact reload checks. The result correctly requires review for three evaluator warnings. Fresh provider-originated delivery, duplicate/retry safety, and source metadata persistence remain open. No test agent ID or new credentials were needed.

## Speaker-attribution follow-up

The [speaker-attribution fix](speaker-attribution.md) preserves Bolna transcript labels, runs role classification in streamed audio, passes attribution into analysis, and persists source call/agent metadata. Both the real transcript path and real browser audio upload passed role/reload checks. Unknown roles require review rather than defaulting the first speaker to the agent. Fresh provider-originated delivery and durable duplicate/retry handling remain open.

## Evidence review and UI milestone — October 25

Implemented opt-in versioned company rules, bounded same-day refund promise and explicit escalation-refusal checks, exact quote evidence, and separate unverified action claims. Deterministic findings persist even when a later model stage fails. Bundled reference knowledge does not activate real policies. Three computed synthetic scenarios are available from Overview without fictional tool results, timing, costs, or company-policy activation.

Overview and Runs now prioritize evidence review, with separate real/demo totals. Call details include Findings, Transcript, Speech diagnostics, and Evaluation checks; quote links reveal transcript context. Settings supports rule creation, editing, disabling, validation errors, and removal. Legacy records remain not assessed. Bolna timing, interruption, and hangup observations persist without inferring network causes.

The current milestone replayed an existing real Bolna execution locally and verified its persisted assessment and provider diagnostics. It did not establish fresh provider-originated delivery or durable retry handling. Policy detection remains limited to supported explicit English patterns. The policy store is single-workspace SQLite. Access control, tenant isolation, durable ingestion, and external action verification remain open. See [reliability details](reliability.md).

## Independent policy benchmark — October 26

Added a separate production-detector evaluation with manually authored expected labels, per-category precision/recall, exact case agreement, evidence integrity checks, and visible expected-versus-detected differences. The fixture has 28 synthetic cases: 24 supported-pattern regressions and four broader challenge paraphrases. Initial result: 25/28 case matches, 10 matched findings, zero unexpected findings, and three misses. The default all-cases CLI gate reports failure on those misses rather than hiding challenge cases. This is a development regression set, not a held-out production accuracy estimate.

The Benchmark page now runs this read-only detector evaluation. Disconnected optimizer weights, improvement-loop controls, and suggestions were removed from the page. Legacy harness consistency remains available under a separate disclosure. Dataset version and hash accompany results. See [policy benchmark methodology and known gaps](policy-benchmark.md).

Validation: 520 Python tests and 21 frontend tests passed; changed Python modules passed Ruff; frontend lint, TypeScript, and production build passed. Local API returned the same 25/28 result. Production secrets, infrastructure, and deployment were unchanged.
