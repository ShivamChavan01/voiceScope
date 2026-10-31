# VoiceScope release readiness, October 31, 2026

## Current local fix follow-up
See [RELEASE_FIXES.md](RELEASE_FIXES.md) for the subsequent independently reproduced blocker fixes, 715 backend/56 frontend tests, real-browser checks and rebuilt-container verification. Earlier results below describe the previous artifact. The packaged policy challenge benchmark still misses 3/28 cases; exact-commit CI and hosted deployment/rollback prerequisites remain unverified. No push, merge or deployment was performed.

## Decision

**CODE-MERGE NO-GO pending CI on this uncommitted patch. DEPLOY NO-GO.**

The local candidate is substantially hardened and verified, but the latest remote
CI still describes the old commit and failed its audit. No push was authorized,
so the updated checks have not run on GitHub. Hosted production also lacks the
new operator credentials, its backend requests timed out, and its backend backup
and rollback prerequisites are unverified. These are release gates, not claims
that the local unit tests failed.

After CI passes, merging main must still be separated from automatic deployment
or wait for the deployment gates. Do not merge into an auto-deploying branch while
its new credentials, data-path compatibility and rollback protection are unverified.

The product boundary is **one company, trusted private operators, one persistent
backend deployment**. Company signup, multi-tenancy, billing and enterprise RBAC
are outside this release. Global company run lookup is intentional. STT key hashing
does not authenticate individual users.

## Revision and starting state

- Branch: `feat/voicescope-reliability-stt-demo`.
- Starting and current Git HEAD: `299666b7df94bacbd046f9e06b3e68c9b15d128b`.
- Target and observed remote main: `f9d459c75e7152e370afed838bc547dde9d0a2d5`.
- The feature branch has four committed changes beyond main, plus this uncommitted
  release patch. Starting working tree was clean; there were no user edits to overwrite.
- No commit, push, PR, merge, production secret edit, production database mutation
  or deployment was performed during this review.
- Runtime/test/configuration source fingerprint: `3e327c0315a18cda250f99152c4f30363235a24f0e3a9bed75f099b30a947b4d`.
  This is a SHA-256 over sorted non-Markdown Git-visible paths and bytes, including
  new files and excluding ignored artifacts. It identifies the tested working tree,
  not a new Git commit.

Review used the complete changed-file inventory/diff against main, focused source
inspection of security/evaluation/persistence paths, static checks and full test
suites. The older branch work includes the existing
STT, speaker, policy, scoring and Calls UI implementation. The file list at the end
identifies this review's additional changes. No visual design changes were made.

## Confirmed issues fixed

| Root cause | Correction and regression evidence |
| --- | --- |
| The shared-key frontend proxy authenticated the server but not visitors. | Standard HTTP Basic operator protection for pages, assets and APIs. Missing or weak configuration returns 503; absent or invalid credentials return 401. The API independently checks authentication so a Proxy-routing bypass cannot expose data. Unit and real-browser tests cover this boundary. |
| Recording enablement was a feature flag rather than visitor authentication. | The flag remains disabled by default and cannot bypass the new operator guard. Browser checks cover enabled-but-unauthenticated access and three encoded-path attempts against a disabled proxy. |
| Ordinary reports could inherit cacheable upstream headers; proxy errors echoed exception messages. | Private responses and upstream fetches use `no-store`; proxy failures return a fixed message. Tests exercise upstream cache headers and a secret-shaped error canary. |
| Provider error strings, exception diagnostics, query snippets, intents and filenames could enter logs or report error fields. | Retain operation/error-type metadata, remove raw provider messages and content snippets, and suppress exception payloads/diagnostic values at both logging sinks. Validation errors omit their input and context. Synthetic privacy regressions cover logs, provider failures, validation and report errors. |
| The webhook downloader followed redirects outside the DNS-pinned STT downloader. | Reuse the existing bounded streaming downloader, public-address resolver, per-hop HTTPS checks and cross-host credential stripping. Existing recording/download tests and webhook tests pass after migrating the mocked network boundary. |
| Replayed completed Bolna events repeated provider evaluation. | Private persistent receipt claims keyed by execution ID; completed replays return the saved run, active claims return 409 with retry advice, failures release their claims, and a report must exist before completion is acknowledged. Tests cover retries, concurrent claims, stale leases and restart persistence. |
| A provider credential needed a narrower scope than a company operator key. | `BOLNA_WEBHOOK_SECRET` authenticates only the Bolna POST ingestion route. Provider-only responses contain acknowledgments, including on replay; an invalid operator key cannot expand that access. Operator `X-API-Key` replay retains the existing full response. |
| Malformed webhook IDs could collide in receipt storage or alter recording paths. | Reject missing, boolean, structured, empty and unsafe IDs before claiming work. Bound body reads while streaming, reject non-object and non-finite JSON, and sanitize malformed execution-field failures. Regression cases run without invoking providers. |
| Report persistence failures were logged while successful responses or SSE complete events were still returned. | Synchronous APIs return an actionable 503; SSE emits an explicit terminal error and no complete event. Successful-stream tests now also verify actual reload from isolated storage. |
| Missing LLM configuration was discovered after an unnecessary cold embedding download. | Initialize the existing provider-dependent report agent before loading policy embeddings. A regression verifies that a missing provider prevents that download. |
| Container defaults did not select the declared persistent data directory; private sidecars and WebM recordings were not excluded explicitly. | Docker defaults `DATA_DIR` to `/app/data`, starts non-root with umask 077, and uses exec for signal handling. Git/Docker rules exclude private data, recordings and SQLite WAL/SHM files. Synthetic context canaries verify exclusion while retaining runtime fixtures. |
| The old Chroma audit waiver had no version or expiry. | Pin 1.5.9 in both dependency declarations, enforce the embedded Rust transport for both clients, and evaluate the full raw audit through a narrowly scoped, expiring policy. No vector-store rewrite or functionality removal. |

## Security audit and remaining vulnerabilities

The current raw Python audit returns five records in ChromaDB 1.5.9, representing
four unique IDs because one advisory is duplicated:

- [PYSEC-2026-311](https://osv.dev/vulnerability/PYSEC-2026-311), CVE-2026-45829.
- [PYSEC-2026-3813](https://osv.dev/vulnerability/PYSEC-2026-3813).
- [PYSEC-2026-3814](https://osv.dev/vulnerability/PYSEC-2026-3814).
- [PYSEC-2026-3815](https://osv.dev/vulnerability/PYSEC-2026-3815).

At review time PyPI's latest release is 1.5.9 and no fixed release is listed.
Chroma is actively used. The described server entry points are absent from the
tested application: both clients are forced to the embedded Rust API, no Chroma
server authorization provider is configured, no Chroma HTTP routes are mounted,
and no new listening sockets appear when the client initializes. Operator-controlled
transport environment variables cannot override the reviewed clients.

The exception applies **only to 1.5.9 and these four IDs, before 2026-11-07 UTC**.
It is an applicability assessment for the private embedded-only boundary, not a
claim that Chroma is patched. The policy prints every exception and blocks other
versions, IDs, packages, newly available fixes, skipped dependencies, malformed scan
results and expiry. CI must also pass the boundary regressions. A separately exposed
Chroma service, untrusted shared storage or a changed transport invalidates this
assessment. See [the complete assessment](docs/chroma-advisory-assessment.md).

The fresh full npm audit returns **19 moderate and 2 low findings, no high or
critical findings**. Most entries trace to minimatch's glob-amplification advisory
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) through
ESLint and shadcn tooling. The low findings trace to deepmerge
[GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4).
These tools process trusted build/CLI inputs; call text is not passed to their glob
or merge APIs. They remain installed and the full audit remains nonzero. Automatic
remediation proposed incompatible consumer downgrades, so none was applied. The
new frontend CI gate blocks high/critical advisories and still prints the lower
severity findings. Review the tooling advisories with the November 7 security
follow-up; do not describe the dependency tree as vulnerability-free.

## Tests and actual commands

Starting baseline: **618 backend tests and 49 frontend tests passed**. Older
590/38, 596/49 and 612/49 reports describe previous snapshots.

| Command/check | Actual result for this review |
| --- | --- |
| `.venv/bin/pytest -q` | 677 passed; one existing Starlette/httpx deprecation warning |
| `npm --prefix frontend test` | 55 passed, zero failed |
| `.venv/bin/ruff check .` | Passed, repository-configured scope |
| `.venv/bin/mypy . --ignore-missing-imports --exclude sdk/` | Passed, 134 files; configured check does not cover all untyped function bodies |
| Frontend `npx tsc --noEmit` | Passed |
| `npm --prefix frontend run lint` | Passed |
| `npm --prefix frontend run build` | Passed, Next.js 16.4.3; includes the new Proxy |
| Raw `pip-audit -r requirements.txt --format json` | Nonzero, five Chroma records as assessed above |
| `python -m tools.dependency_audit` in the isolated pip-audit 2.10.1 environment | Exit 0 with four explicit, deduplicated temporary exceptions |
| Full `npm audit --json` | Nonzero, 19 moderate and 2 low findings; none high/critical |
| Frontend `npm audit --audit-level=high` | Exit 0 with the lower-severity warnings retained |
| `.venv/bin/python scripts/run_benchmark.py --min-truth 0.7` | Passed on 10 synthetic fixtures; hallucination accuracy is explicitly unmeasured |
| `.venv/bin/python scripts/run_reliability_benchmark.py --json PATH` | Nonzero at its unchanged 100% default: 25/28 cases, 24/24 supported patterns and 1/4 challenge paraphrases; TP=10, FP=0, FN=3 |
| `docker build -t voicescope-release-review:final .` | Passed |
| Full backend suite in the non-root Python 3.11 production image | 677 passed |
| Image mypy and Ruff | Passed; 133 packaged source files checked by mypy; optional local audio-generator script excluded from the image |
| Docker context canaries | Zero private files included; application JSON/policy fixtures retained |
| Container smoke, named-volume replacement and restart | Passed; restored three synthetic runs, retained receipt, verified default data directory and 0600 SQLite mode |
| Container missing-provider and retention checks | Passed; explicit SSE error, audio 200 before expiry and 404 after expiry, expired metadata unavailable, primary report retained |
| `node frontend/tests/private-access.browser.mjs` | Passed against the production-mode local frontend; unauthenticated access, middleware-header bypass, static assets, cross-origin and disabled encoded-STT paths checked |
| `node frontend/tests/calls-ui.browser.mjs` | Passed, five tabs, evidence links, uploads, empty-stream errors, focus and mobile checks; zero page errors and no provider uploads |
| `node frontend/tests/stt-demo.browser.mjs` | Passed with real original audio, timestamp seek, both transcripts, reload and controlled expiry response; zero page errors or additional provider uploads |
| Private local SQLite online backup/restore rehearsal | Passed; restored original run text in an isolated directory without changing the source databases |
| `git diff --check` and targeted configured-secret/static-bundle scan | Passed; zero configured-secret/private-key matches, including public static bundles; real transcript/recording URL/phone values absent from the isolated backend log |

Browser scripts use the existing installed Chrome and an isolated Playwright 1.64.1
tool installation under ignored `.gstack/release-review/browser-tools`; no project
dependency was added. Credentials are supplied through private process configuration,
never command arguments or source. Private logs, bodies, recordings and detailed
evidence remain under ignored `.gstack/release-review/` and must not be published.

## Remote CI

[Run 41174064636](https://github.com/ShivamChavan01/voiceScope/actions/runs/41174064636)
is for `299666b`, not this working-tree patch. Lint, test, frontend, typecheck and
benchmark passed. Audit failed; Docker was **skipped**, not passed. The updated
workflow and exception policy require a new run after an explicitly approved push.
Local equivalent checks do not turn the old remote run green.

## Real Bolna acceptance

An existing authorized completed execution was fetched through Bolna's API and
replayed through the local authenticated receiver. Its original transcript and
source call/agent metadata survived evaluation, persistence and reload. A repeated
event returned the same run without another evaluation. The original recording
was retrieved through Bolna and its byte hash verified. One Deepgram pass produced
39 timestamped reference segments from the approximately 68.48-second recording.
Repeated preparation, page reloads and browser inspection reused that reference.
The isolated backend recorded **one completed Deepgram submission**.

The final cached replay after a backend restart also verified that provider-only
credentials return only acknowledgments, including when an invalid operator key is
added. An authenticated operator still retrieves the full report. Invalid API keys
return 401; a different key cannot retrieve the cached private audio and returns 404.
The local dashboard total matches persisted run rows and the demo/real partition.

This is **controlled replay, not fresh Bolna-originated delivery**. No new phone
call was placed and no agent settings were changed. Real-call provider processing
was exercised during the review; subsequent boundary-only edits were covered by
regressions and cached replays rather than resubmitting recordings after every edit.

The real STT comparison stays **Not scored**, metric null. Trusted Bolna utterance
timestamps and caller mapping are still missing. No human reference or confirmed
STT error was invented. Audio playback and reference-timestamp navigation work;
aligned real-call finding navigation remains unavailable because this call has no
aligned findings. Synthetic fixtures exercise that evidence-navigation path.

## Hosted deployment and rollback

Vercel access was verified after team authorization. Observed configuration:

- Project `voice-scope`, root `frontend`, Node.js 24.x.
- Production alias `voice-scope.vercel.app` points to Ready deployment
  `dpl_BX9ycxRaTwQBND67XkWiCovkrGeV`, commit `f9d459c...`, created September 8.
- SSO protection is `all_except_custom_domains`; project password protection and
  trusted-IP protection are disabled. The production root responds without auth.
- Returned environment inventory has `API_KEY` and `BACKEND_URL` for production,
  plus legacy `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_API_KEY` for production/preview.
  No operator-auth variables or STT proxy enablement are configured in that inventory;
  the hidden production-variable count is zero. Values were not decrypted or printed.
- The current main and candidate client code do not reference `NEXT_PUBLIC_API_KEY`.
  Its existence is a configuration risk to review, not proof of a leaked key. Remove
  it only through an approved configuration change; do not use it as a server-key fallback.
- Current unauthenticated production root GET returned 200. Health and one limited
  run-list request each timed out after 20 seconds. No live call data was returned
  by those probes. This does not prove an outage or successful visitor-data protection.
- Older production artifacts `dpl_Gij8GmXuJYX6fs4f6kNN1LMBgwMX` and
  `dpl_9YNnaJ5tZzRsLchKXrEMQgZSyJs1` also report Ready. No production rollback
  was executed. Ready artifact availability is not a completed rollback rehearsal.
- Railway CLI and Railway API/project tokens are unavailable. The deployed backend
  image, service settings, data-volume binding, production backup and restore
  procedure remain unverified. No production database was opened or changed.
- Verify existing `DATA_DIR` and database-path overrides before applying the new
  Docker default. An existing database outside `/app/data` needs an approved
  backup/migration plan; do not mistake an empty new directory for a clean install.

**Do not roll back to an old public frontend without an independent private access
gate.** The historical artifacts lack the new operator authentication. A rollback
must retain verified external protection or target an authentication-preserving
baseline. Local named-volume replacement and SQLite restore checks do not establish
that hosted rollback is safe.

The new frontend deliberately returns 503 until private operator credentials are
configured. A merge into an auto-deploying main branch could therefore affect
availability. First verify the Git-to-deployment connection and approve private
Preview/server-only configuration and rollback protection. Nothing in this review
authorized or changed those settings. See [deployment steps](docs/private-operator-deployment.md).

## Known product limits

- Post-call analysis only; no change to live calling or real-time speech repair.
- Model summaries and heuristic consistency scores are not ground-truth accuracy.
  Numeric support checks do not establish semantic/world truth. Unknown or invalid
  inputs remain unassessed/failed rather than receiving a fabricated score.
- Only two bounded English policy kinds are supported. The three challenge misses
  remain visible. Missing refund-tool evidence produces an unverified claim, not a
  confirmed failed refund. No tool execution evidence is fabricated.
- Speaker inference is labeled and is not treated as confirmed caller identity.
  Automatic transcription disagreement is distinct from human-reference WER.
- Webhook evaluation is synchronous. Receipts require the same persistent volume;
  there is no distributed queue or exactly-once provider guarantee across a crash.
  Historical runs are not backfilled into receipts and changed completed payloads
  are not automatically re-evaluated. Old duplicate evaluations remain separate
  persisted runs in the dashboard's explicit all-time run scope.
- STT submission sharing is per backend worker. Use one worker for the reviewed
  private deployment; independent workers can duplicate a reference submission.
- STT expiry is 24 hours after last write and cleanup is opportunistic on access.
  Primary run/receipt retention is separate. Expiry does not revoke downloaded
  audio or browser buffers. At-rest encryption and production backup policy belong
  to the deployment environment and were not established by this module.
- Basic authentication uses one private operator credential and browser credential
  caching. It provides no individual operator audit identity or enterprise session
  management. This matches the stated company boundary, not a multi-user SaaS claim.
- Actual cloud PostgreSQL/TLS behavior, fresh hosted Bolna delivery and production
  backup/restore remain unverified. No unit test is presented as proof of them.

## Remaining gates

1. Review this local patch and explicitly approve a feature-branch push. Require
   every updated CI job, including Docker, to finish green; assess printed warnings.
2. Approve and configure private operator access and server-only Preview credentials.
   Verify external HTTPS/authentication before considering production. Preserve access
   protection through rollback. No production secret changes are implicit here.
3. Supply secure Railway project/service inspection access, identify the deployed
   backend image and data bindings, verify a production backup and isolated restore,
   and record a rollback plan that preserves private access.
4. Before hosted integration sign-off, configure Bolna's documented custom header
   through an approved change and verify an actual completed-call delivery and retry.
5. Reassess the Chroma exception before November 7 or immediately when a patched
   compatible release is available; review the remaining npm tooling warnings.

These gates are about verification and private deployment, not building tenancy,
billing, extra voice platforms or a new transcription pipeline.

## Files changed in this release review

- `.dockerignore`
- `.github/workflows/ci.yml`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `RELEASE_READINESS.md`
- `STT_DEMO_READINESS.md`
- `agents/analysis_agent.py`
- `agents/report_agent.py`
- `agents/transcription_agent.py`
- `api/routes.py`
- `api/sse.py`
- `core/batch.py`
- `core/knowledge_base.py`
- `core/pipeline.py`
- `core/stt_recording.py`
- `docs/chroma-advisory-assessment.md`
- `docs/merge-readiness.md`
- `docs/private-operator-deployment.md`
- `docs/stt-live-verification.md`
- `docs/stt-quality.md`
- `frontend/src/app/api/[...path]/route.ts`
- `frontend/src/lib/operator-auth.ts`
- `frontend/src/proxy.ts`
- `frontend/tests/calls-ui.browser.mjs`
- `frontend/tests/operator-auth.test.mjs`
- `frontend/tests/private-access.browser.mjs`
- `frontend/tests/stt-demo.browser.mjs`
- `frontend/tests/stt-proxy.test.mjs`
- `llm_providers/registry.py`
- `main.py`
- `middleware/auth.py`
- `pyproject.toml`
- `requirements.txt`
- `storage/chroma_client.py`
- `storage/chroma_store.py`
- `storage/db.py`
- `storage/webhook_receipts.py`
- `tests/test_chroma_security_boundary.py`
- `tests/test_dependency_audit.py`
- `tests/test_error_privacy.py`
- `tests/test_pipeline_integration.py`
- `tests/test_private_responses.py`
- `tests/test_speaker_integration.py`
- `tests/test_sse.py`
- `tests/test_stt_review_api.py`
- `tests/test_webhook_receipts.py`
- `tests/test_webhooks.py`
- `tools/__init__.py`
- `tools/dependency_audit.py`
- `utils/logger.py`
