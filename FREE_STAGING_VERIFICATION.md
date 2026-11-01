# Free staging verification — November 1, 2026

**Status: prepared and tested locally; NOT DEPLOYED.** No Render service or Vercel project was created. No production configuration, database, volume, DNS, branch, billing or live Bolna callback was changed. No paid provider call was made.

## Release and URLs

| Item | Exact status |
| --- | --- |
| Branch | `feat/voicescope-reliability-stt-demo` |
| Base Git commit | `3bd5a31e55e486feb71c9469b424845fef36080c` |
| New staging commit | **None. Changes are uncommitted and unpushed.** Old green CI does not cover this patch. |
| Deployed staging commit | **None — deployment approval is required.** |
| Render staging URL | **Not assigned; service not created.** Proposed name: `voicescope-staging-demo`. |
| Vercel Preview URL | **Not assigned; isolated project/Preview not created.** |
| Local production-mode frontend | `http://127.0.0.1:3259` during QA only; not a hosted acceptance result |
| Local backend | `http://127.0.0.1:8259` during QA only |
| Existing production | Render `voicescope-80mu.onrender.com` and Vercel `voice-scope.vercel.app`; never used as staging targets |

Starting worktree already contained Railway preparation, `HOSTED_RELEASE_VERIFICATION.md`, `docs/staging-acceptance.md`, `render.staging.yaml` and deployment configuration tests. That work was preserved. Railway configuration is inactive for Render and is not a Render startup setting. No Git reset, commit, push, merge, PR or deployment was performed.

Final non-Markdown candidate fingerprint (sorted Git-visible paths, NUL, file bytes, NUL; including tests): `57a9c7803b80da39223c0d8c79317c861a718ea4081b9c28044953175ad07420`. Runtime/configuration fingerprint excluding test directories: `740b36a5c5c5dcee9cb31824d3353a7530c64073b3ded9122d7da02afe25cdcb`. Final frontend build ID: `u9ozsPL0_o6JotbXwQqx0`. The ignored private artifact manifest records the same values. Report edits do not change these non-Markdown fingerprints.

## Implementation files

New implementation: `core/staging.py`, `core/staging_demo.py`, `middleware/staging_demo.py`, and the public synthetic asset `core/data/staging_audio.json`. Startup/API wiring: `main.py`, `api/routes.py`. Live-service backstops: `llm_providers/registry.py`, `stt_providers/registry.py`, `core/stt_recording.py`. Synthetic source handling reuses `core/stt_quality.py`, `core/stt_sources.py`, and `core/stt_service.py`.

Frontend changes are limited to synthetic provenance/evidence handling in `frontend/src/lib/api.ts`, `frontend/src/lib/stt-quality.ts`, `frontend/src/components/call-review.tsx`, `stt-review.tsx`, `stt-transcripts.tsx`, and `stt-results.tsx`. The existing five-tab layout and production access design remain intact; no CSS redesign was added.

Tests: `tests/test_free_staging.py`, the existing local deployment-config preparation, `frontend/tests/stt-quality.test.mjs`, `frontend/tests/call-review.test.mjs`, and opt-in `frontend/tests/free-staging.browser.mjs`. `render.staging.yaml` enables only synthetic mode. No package version or Dockerfile change was required.

## Storage audit

`DATABASE_URL` is not universal persistence. Production Render metadata points to Neon PostgreSQL; this pass did not connect to production Neon or read its records.

| Subsystem | Existing storage and staging configuration | Free-instance behavior |
| --- | --- | --- |
| Reports, call metrics, alert data | `storage/monitoring.py`: PostgreSQL when the pool is available; otherwise SQLite at `MONITORING_DB_PATH` or `DATA_DIR/monitoring.db` | Staging deliberately uses isolated SQLite; ephemeral |
| Provider cost ledger | `storage/cost_store.py`: PostgreSQL or `COST_DB_PATH` / `DATA_DIR/costs.db` | Ephemeral fallback; fixture provider costs are zero because no provider ran |
| Explicit company rules | `core/policy_store.py`: `POLICY_DB_PATH` / `DATA_DIR/policies.db`, SQLite | Ephemeral; fictional fixtures restored if missing |
| User knowledge entries | `core/knowledge_store.py`: `KNOWLEDGE_DB_PATH` / `DATA_DIR/knowledge.db`, SQLite | Ephemeral |
| QA cohorts and scores | `core/qa.py`: `QA_DB_PATH` / `DATA_DIR/qa.db`, SQLite | Ephemeral |
| Extraction schemas/results | `core/extractions.py`: `EXTRACTIONS_DB_PATH` / `DATA_DIR/extractions.db`, SQLite | Ephemeral |
| STT audio, transcripts, annotations and review | `storage/stt_reviews.py`: `STT_REVIEW_DIR` / `DATA_DIR/stt_reviews/reviews.sqlite`, owner/API-key-hash scoped, directory 0700/file 0600 | Ephemeral; normal artifacts expire 24 hours after the last write |
| Bolna delivery receipts | `storage/webhook_receipts.py`: `DATA_DIR/webhook_receipts/receipts.sqlite`, 600-second processing leases | Ephemeral; no restart-spanning provider deduplication claim on Free |
| Chroma call/knowledge collections | `storage/chroma_store.py` and `core/knowledge_base.py`, explicit `CHROMA_PERSIST_DIR=/app/data/chroma_db` | Local filesystem; ephemeral, not moved to Neon |
| Optimizer state | `core/optimizer.py`: local `OPTIMIZER_DB_PATH` / `DATA_DIR/optimizer.json` | JSON, not SQLite; ephemeral |

Normal database initialization checks `DATABASE_URL`, creates an asyncpg pool and applies the existing schema. Pool failures can fall back to SQLite, so a public health response is not proof of Neon connectivity or durability. New synthetic-only startup rejects any nonempty external `DATABASE_URL` **before** database initialization. No separate Neon database is required for this disposable demo. A later persistent-report experiment would require a separately authorized staging database and would still leave STT/receipts/Chroma local.

The existing Dockerfile is reused unchanged: non-root user, private umask 077, writable `/app/data`, and Uvicorn binds `${PORT:-8000}`. The local container test explicitly used `PORT=10000` and reached `/api/v1/health`. That endpoint is lightweight liveness; it does not certify providers, database connectivity or RAG readiness.

Chroma's persistence includes its internal SQLite database and vector-index files. Normal embedding use also needs a writable model-cache directory in the non-root user's home. The fixture seeder does not initialize embeddings or download a model; no live-RAG memory claim is made. In normal mode, the knowledge index has a `/tmp/chroma_db` default distinct from the call store's `DATA_DIR` default, so staging explicitly sets `CHROMA_PERSIST_DIR` for both.

## Free Render configuration and safety

`render.staging.yaml` specifies one separate Docker web service, **plan `free`**, one instance, no disk or database resource, feature-branch source, automatic deploys off, and HTTP health `/api/v1/health`. Render's authenticated Blueprint validator returns `valid: true` with exactly one planned service action. Validation did not apply that action.

Required backend configuration:

- `STAGING_DEMO_ONLY=true`, `APP_ENV=production`, `PYTHON_DOTENV_DISABLED=1`.
- Separate `VALID_API_KEYS` with keys at least 24 characters; distinct staging-only `BOLNA_WEBHOOK_SECRET`.
- Absolute isolated `DATA_DIR=/app/data`; report, policy, knowledge, cost, STT and Chroma paths inside it.
- **No `DATABASE_URL`, production credentials, environment-group imports, or provider API keys.**
- Existing STT/LLM provider names may remain selected, but synthetic mode prevents acquiring cached or new providers and prevents recording network downloads. No new transcription provider was added.

Synthetic-mode startup rejects external databases, provider credentials, weak/missing API keys, root/relative data directories and storage overrides escaping `DATA_DIR`. Authenticated live-processing/upload/webhook/reference/recording-download operations return explicit 503 responses. They do not acknowledge fake ingestion or run a provider. Authentication runs before this rejection. Normal production behavior remains enabled when this opt-in flag is absent.

The guard is deliberate and visible: this is a synthetic-only environment, not a claim that the complete live Bolna/LLM pipeline ran with no credentials. No core implementation was removed to fit Free memory. Live RAG/embedding or model-provider workload memory is not proven by this fixture run.

## Synthetic experience

Startup restores six reserved fixtures using the existing monitoring and STT stores. Authenticated `POST /api/v1/demo/staging` can restore them after deliberate deletion or expiry. It is unavailable outside demo mode. Known fixture IDs are idempotent; unrelated data at a reserved ID causes an error rather than an overwrite. Existing reviews/policy edits are not rewritten merely by restarting. Regeneration restores only public synthetic fixtures, never real expired recordings or production data.

| Scenario | What actually executes | Honest presentation |
| --- | --- | --- |
| `demo-staging-compliant` | Existing deterministic policy matcher | No supported match; no overall compliance claim |
| `demo-staging-policy` | Same-day refund guarantee detector | Confirmed fictional-policy rule match with quote and policy snapshot |
| `demo-staging-escalation` | Explicit refusal detector | Confirmed rule match; transcript evidence navigation |
| `demo-staging-hallucination` | Displays a supplied contradiction label and its two source turns | **Hand-labeled synthetic example. No live semantic detector ran.** This does not verify production hallucination detection. |
| `demo-staging-stt` | Existing time/role comparator on authored `100` versus `-100` transcripts | **20.0% synthetic fixture disagreement**, one substitution / five reference words, Needs human review; not model accuracy or human WER |
| `demo-staging-not-scored` | Same comparator with original timestamps absent | **Not scored**; no aggregate metric or confirmed error |

`core/data/staging_audio.json` contains intentionally public synthetic speech generated offline with eSpeak, compressed and hash-checked. The spoken script and generator provenance are included. No human/customer recording or transcript was copied into this environment. Whole-utterance fixture timing comes from the generated audio and known 0.6-second lead-in; it is not fabricated Bolna timing. No diarization speaker number is assumed to be caller identity. Fixture roles are labeled as authored metadata.

The existing STT module is reused, with an explicit `synthetic` provenance variant and matching UI labels. Automatic references remain distinct from verified human references; synthetic references cannot declare human verification. Fixture metadata must not pre-check the operator's personal listening confirmation. Existing real Bolna/Deepgram/human behavior remains covered by the normal suites.

## Isolated Vercel Preview preparation

A private, unapplied request is in ignored `.gstack/free-staging/vercel-preview.private.json`. It proposes a **new isolated project**, root `frontend`, with no Git repository auto-link, then a manually selected Preview at the reviewed commit. This avoids inheriting the production project's legacy public-key-named variables or auto-deploying main. Confirm available free account quota and permissions before creating it; no plan upgrade is authorized.

Only Preview-targeted, server-side `OPERATOR_AUTH_USER`, `OPERATOR_AUTH_PASSWORD`, `BACKEND_URL`, `API_KEY` and the private STT proxy flag are prepared. The operator password and API key are newly generated staging values; no `NEXT_PUBLIC_*` credential is added. `BACKEND_URL` is still an explicit placeholder until Render assigns the new service origin. Do not apply the request while that placeholder remains. Private values stay in mode-0600 files under ignored mode-0700 evidence directories, never in Git or this report.

The application keeps Basic authentication on pages/assets/API, exact origin checks, encoded-path validation and no-store responses. Vercel protection can add another gate; a platform sign-in redirect alone is not an application-auth test. No Vercel project, setting or deployment was changed in this pass.

## Executed verification

Evidence directory: ignored `.gstack/free-staging/`. These are **local** results.

| Command/check | Exit | Actual result |
| --- | --- | --- |
| Provider-guard regressions before implementation | 1 | Three failures: cached STT/LLM access and provider configuration were not blocked by the previously unsupported demo flag |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest -q tests/test_free_staging.py` | 0 | 22 passed; isolation, no provider/network calls, unsafe DB rejection, idempotency, expiry/reseed and private report/audio hydration |
| First full backend run | 1 | 739 passed; one 60-second bootstrap subprocess timeout during concurrent builds; failure retained |
| Bootstrap alone, unchanged timeout/assertions | 0 | 1 passed in 49.61 seconds |
| Final full backend run | 0 | **742 passed**, one existing Starlette/httpx deprecation warning, 154.86 seconds |
| `npm --prefix frontend test` | 0 | **58 passed**, no skipped tests; includes synthetic provenance, evidence and no human-verification claims |
| Ruff / mypy | 0 / 0 | Configured full checks pass; mypy checks 140 source files and retains notes about unchecked untyped bodies |
| `npx tsc --noEmit` / `npm run lint` in frontend | 0 / 0 | Standalone TypeScript and ESLint pass |
| Fresh isolated `npm ci` and final `npm run build` | 0 / 0 | Production frontend build, no application dotenv copied |
| `render blueprints validate render.staging.yaml --output json` | 0 | Render accepts the Free proposal; exactly one service planned, none created |
| `docker build -t voicescope-free-staging:verified .` | 0 | Existing Dockerfile builds final backend candidate |
| Local container with `--memory 512m --memory-swap 512m --cpus 1`, no mounted data volume | 0 | Non-root, writable data dir, seeded calls, private media, provider rejection and empty-filesystem replacement recovery |
| `frontend/tests/free-staging.browser.mjs` against real isolated production-mode frontend/API | 0 | Ten journeys: access, calls, evidence, policy, STT/seek, reload, Not scored, mobile, cross-origin denial and explicit live-processing failure |
| Existing `private-access.browser.mjs` against isolated frontend and disabled-STT variant | 0 | Actual protected font/assets, policy CRUD, authentication and path checks |
| Private HTTP harness | 0 | 32 checks, no failures; every response no-store; actual generated backend key/operator password absent from client bundles |
| Full policy benchmark at original threshold | 1 | Known **25/28**, supported 24/24, challenge 1/4; TP10 FP0 FN3. No threshold or fixture-label weakening |
| Whitespace and secret/private-file review | 0 | No configured credential/private-file matches or files over 5 MB; generated synthetic audio asset is intentional |

The initial new UI parser test caught a missing `synthetic` review-source allowance; the boundary validator was corrected, retaining rejection of fabricated human verification. One shell helper initially used a repository-relative interpreter from the frontend directory; it was rerun with the correct working directory. Initial browser attempts used a frontend route outside its allowlist and omitted the disabled-proxy test URL; the harness was corrected to exercise the actual upload route and an explicit disabled variant. Assertions were retained. Final synthetic labels/build were rebuilt and rechecked rather than reusing an older bundle.

Final browser evidence has zero uncaught page errors, zero reference submissions, one expected console 503 from deliberately blocked live processing, and recorded `ERR_ABORTED` navigation/media cancellations. Do not summarize this as zero network events of every kind. Screenshots are retained privately under `.gstack/free-staging/browser/`.

## Resource findings

Final local image: `voicescope-free-staging:verified`, `sha256:ebd90989bd59113761bbcf243b137dd5b30d6d4aea1eea1d674d17e0cc94738a`.

Under the hard 512 MiB/no-swap container limit, final cold HTTP health took **36.66 seconds**. Replacement of the container with an empty writable filesystem reached health and regenerated fixtures in **60.85 seconds**. The replacement container's cgroup memory high-water mark was **150.05 MiB**, with no observed OOM. An earlier local iteration took 50.12 seconds to health and sampled up to 162.6 MiB.

These tests used **one local CPU**, not Render Free's current 0.1 CPU allocation. They do not establish hosted startup latency, reliability or full live-pipeline memory use. The first bootstrap timeout under concurrent host load remains recorded; resource contention is an explanation consistent with the successful reruns, not a separately profiled root-cause proof. No timeout was increased and no assertion disabled to obtain a pass.

Render Free can idle-sleep, shares included usage quotas, lacks persistent disks and has an ephemeral filesystem. A Free plan is not an unlimited-build/bandwidth or zero-overage guarantee. No billing change or paid infrastructure purchase was made. Before execution, confirm free quota; stop on a payment-required response rather than falling back to a paid plan. See [Render Free limits](https://render.com/docs/free).

## Actual hosted checks — not performed

All new hosted-staging acceptance rows are **PENDING**: assigned URLs and deployed SHA, cold/warm readiness, HTTP auth/private API/media, calls/reports, synthetic STT/policy/evidence, browser/mobile/errors, restart/reseed, host memory and usage limits. The user expressly required explicit deployment approval. Neither the current production URLs nor local tests are substitutes for these rows.

No hosted backup/restore, Neon connection, live Bolna webhook, recording retrieval, independent Deepgram transcription or live hallucination-model evaluation was run. In synthetic-only mode those live actions are intentionally disabled. The Chroma 1.5.9 temporary exception still expires **before November 7, 2026 UTC**; it was not extended or described as a patch. No dependency version or audit ignore was changed. Fresh dependency auditing and exact-commit GitHub CI are required before deploying a new commit; prior green CI only covers its original SHA.

The three known paraphrase misses remain `challenge-assure`, `challenge-lead`, `challenge-returned`. Synthetic development metrics are not production accuracy. The legacy benchmark does not cover those misses.

## Readiness and remaining steps

- **Local synthetic demo: GO**, within the explicit no-provider/ephemeral limitations.
- **Prepare isolated Free staging: GO.** Manifest validated; private credentials and Preview proposal ready locally.
- **Hosted demo acceptance: PENDING** until the new reviewed commit is approved, pushed, passes its own CI, deployed to isolated Free services, and tested at their actual URLs.
- **Production: NO-GO.** No production promotion, durable-STT/receipt guarantee, hosted recovery verification or applicable-vulnerability remediation is implied.

Required next approval: review and authorize the specific staging patch/commit and feature push, then the new Free Render service and isolated Vercel Preview only. Confirm free quotas before applying; do not reuse production Neon, change DNS, upgrade plans, attach paid disks, connect production Bolna webhooks, or add paid provider credentials. No additional Neon database is needed for this ephemeral fixture demo. If persistent reports are later required, authorize a separate Neon staging database; that alone still does not make the local subsystems durable.
