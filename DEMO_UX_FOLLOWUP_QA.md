# Demo UX follow-up QA — November 2, 2026

**Verdict: CONDITIONAL PASS.** Both requested defects are fixed and verified locally. Hosted staging still runs the previous code. No commit, push, merge, deployment, production/Neon operation, billing change or paid provider call occurred. Controlled managed Render cold-start verification remains pending.

## Repository and evidence

- Branch: `feat/voicescope-reliability-stt-demo`.
- Starting and final HEAD: `6a9e9daa637656e74686ae0a79b771b64b0c4b70`; these fixes are uncommitted and unstaged on top of it.
- Existing changes to `FREE_STAGING_VERIFICATION.md` and `railway.toml`, and untracked `HOSTED_RELEASE_VERIFICATION.md`, `STAGING_HARDENING_DEPLOYMENT.md`, `docs/staging-acceptance.md`, `tests/test_deployment_config.py`, were preserved.
- Tested code/config fingerprint: `9c84e0d86dafef26382cc9a0001e1857d9e21f25893fc2429a6e11f46d6153ee`. SHA-256 of sorted Git-visible code/config paths, NUL, bytes, NUL; Markdown excluded. Includes existing visible changes and tests. Runtime files match the isolated source snapshot.
- Private evidence: ignored `.gstack/demo-ux-followup/`. Known private key/password scan found no matches in Git-visible files or the 22 final compiled static files.
- Applied pstack root-cause and proof-of-work principles. Model-role configuration was read; no provider routing or credentials were changed. No subagents were used or claimed as reviewers.

## Issue 1 — processing and assessment were presented as one concept

**Reproduced before editing.** Hosted `/api/v1/runs` returned six `completed` calls: two confirmed policy matches, one assessed call with no findings in two supported checks, and three calls without structured policy reports. Selecting the option labeled **Review required** sent `status=partial`, correctly returning zero processing-incomplete calls. It never queried policy findings.

**Root cause:** `frontend/src/app/runs/page.tsx` labeled processing state `partial` as Review required. `api/routes.py` accepted only a processing `status` parameter, and `MonitoringStore.get_runs()` filtered only the persisted processing state. A completed evaluation containing a policy finding is legitimately completed; changing its persisted state would conflate two domains.

**After:**

- Processing options are **All processing states / Processed / Processing incomplete / Processing failed**.
- A separate policy-assessment selector offers **Policy match found / No matches in supported checks / Not assessed / Needs evidence review / Insufficient policy evidence**.
- Existing assessment badge semantics are retained. Confirmed policy matches take precedence, then review findings, insufficient evidence, and a scoped no-match result. Missing or invalid structured reports remain Not assessed.
- The backend validates `assessment` and supported processing states. Unknown values return 422. Search, processing and assessment combine before pagination; returned totals describe the entire filtered result, not only the first 50 loaded rows.
- Classification reuses validated `reliability_summary` values. The same bounded-batch filter is used with SQLite and PostgreSQL query adapters; no schema or persisted status was changed. Batches fetch 200 candidates and retain only the requested result page.
- `created_at DESC, run_id DESC` supplies stable ordering across batches when timestamps tie. This was added after the second-pass review; the PostgreSQL query-contract regression failed before the explicit tie-breaker. An existing SQLite tie case already passed and was not misreported as a reproduced SQLite defect.
- Search is stored with history replacement while dropdown changes create history entries. Back/Forward, reload and direct call URLs restore filters. Closing a call preserves filters, other query parameters and hash. Invalid filters show an API validation error and can be cleared with Reset filters.
- Loading state changes follow filter events and URL changes; call-only history navigation does not leave the list stuck loading. No-match wording remains scoped to supported checks, never overall compliance.

## Issue 2 — a correct real-only count lost its scope in the UI

**Reproduced before editing.** The hosted Overview footer said **0 calls have no structured assessment** while Calls showed three synthetic records as Not assessed. The API returned `total_calls=6`, `demo_calls=6`, `real_calls=0`, `legacy_calls=0`.

**Root cause:** `MonitoringStore.get_run_summary()` intentionally excludes reserved `demo-*` IDs from `legacy_calls` and the policy assessment counters. Its computation was correct. The footer in `frontend/src/app/page.tsx` omitted that real-only scope, making the count look like it covered all six displayed examples.

**After:** the footer explicitly says **Real inputs without a structured policy assessment: 0 of 0. Synthetic examples are excluded from assessment counts.** Stored calls still show **0 real inputs · 6 synthetic**. Existing real-only metric descriptions remain visible. No backend summary metric, denominator or fixture identity was changed.

The API client now validates the summary response before displaying it: required counts must be safe nonnegative integers, real plus synthetic must reconcile with total, scoped counters must fit their denominators, rates must be finite/in-range or unavailable, and scope must be supported. Malformed or partially populated responses produce an actionable Overview error rather than invented zeros. The empty public-demo state no longer invites unavailable uploads or seeding.

## Tests and executed results

Exact files changed by this follow-up:

- Backend: `api/routes.py`, `storage/monitoring.py`.
- Frontend: `frontend/src/app/page.tsx`, `frontend/src/app/runs/page.tsx`, `frontend/src/components/overview-coverage.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/call-navigation.ts`, `frontend/src/lib/run-summary.ts`.
- Tests: `tests/test_run_assessment_filters.py`, `frontend/tests/benchmark.test.mjs`, `frontend/tests/call-navigation.test.mjs`, `frontend/tests/stt-quality.test.mjs`, `frontend/tests/upload-stream.test.mjs`, `frontend/tests/demo-ux-followup.browser.mjs`, `frontend/tests/overview-coverage.test.mjs`, `frontend/tests/run-summary.test.mjs`.
- Report: `DEMO_UX_FOLLOWUP_QA.md`. Existing unrelated files listed above are outside this fix.

| Check / command | Status | Actual evidence |
| --- | --- | --- |
| Baseline `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest tests/test_run_summary.py tests/test_reliability_api.py tests/test_free_staging.py -q` | PASS | 71 passed; `baseline.log`. This was a targeted baseline, not a rerun of every prior test. |
| Initial new backend regressions | FAIL before fixes | 11 failed, 3 passed; assessment query was ignored and invalid filters were accepted. `backend-before.log`. |
| Initial footer regression / new contracts | FAIL before fixes | The unscoped footer failed its first check; new coverage/summary contract modules did not yet exist. The final footer test renders visible text rather than depending on a component name or source substring. |
| Final full backend `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest tests/ -q` | PASS | **830 passed**, one existing Starlette/httpx deprecation; `backend-final.log`, exit0. Includes five pre-existing untracked deployment tests outside this fix. |
| Targeted assessment and summary suites | PASS | **26 passed**; `backend-final-targeted.log`. |
| `cd frontend && npm test` | PASS | **74 passed**, no failures/skips; `frontend-verified.log`. |
| `npx tsc --noEmit` | PASS | No TypeScript errors; `types-verified.log`. |
| `npm run lint` | PASS | No ESLint errors; `eslint-verified.log`. |
| `.venv/bin/python -m ruff check .` | PASS | `ruff-verified.log`. |
| `.venv/bin/python -m mypy . --ignore-missing-imports --exclude sdk/` | PASS | 142 source files; existing notes about untyped bodies remain. `mypy-final2.log`. |
| Isolated `npm run build` | PASS | Production-mode build with synthetic Preview settings, exit0; `build-final.log` and `build-final.exit`. |
| Real local Chromium acceptance | PASS | **13 journeys**, zero page errors and zero reference-generation submissions; `browser-verified.log`, `browser-verified/results.json`. |
| Read-only/API/STT/detector regressions | PASS | Existing full backend/frontend suites plus the browser scenarios below. The authored benchmark still returns 28/28; this is not production accuracy. |
| Private-artifact scan and `git diff --check` | PASS | No known secret matches, no runtime snapshot differences, no whitespace errors; `final-source-review.json`. |
| Controlled managed Render cold sleep/wake | NOT TESTED | No hosting restart, deployment or forced idle experiment was performed. An initial health200 is not proof of a cold start. |
| New hosted-code acceptance / new GitHub CI | BLOCKED | Requires approval to commit/push and later deploy both staging components. Old CI/staging cannot validate this working tree. |

Intermediate failures were retained: mypy caught an untyped nested page helper; ESLint rejected synchronous loading-state updates inside an effect; three data-URL test loaders needed the new summary module mapping. These were corrected without suppressions or weaker assertions. The first browser pass failed a 650ms audio-position check while media could still be buffering. A separate actual-media trace showed seeked at0.6 followed by normal advancing playback, without a reset. The final test waits for ready media and completed seeking before retaining the same advancing-position assertion. No audio implementation was changed in this follow-up.

## Regression coverage and browser evidence

`tests/test_run_assessment_filters.py` adds 20 cases covering all six canonical fixtures; the 2/1/3 assessment split; search matches and Unicode nonmatches; processing/assessment combinations; filtering before pagination; invalid query values; real-only, synthetic-only, mixed and empty datasets; malformed/insufficient/unverified reports; more than 200 candidate rows; and stable equal-timestamp pages. Existing summary tests continue to pass. PostgreSQL adapter and query ordering are tested with mocks; no live PostgreSQL or Neon connection was used.

Frontend tests cover:

- Explicit real-only text for zero-real/all-synthetic and real-only coverage.
- Empty, synthetic-only and real-only summary responses; rejection of missing, negative, wrong-type, unsupported-scope or inconsistent data.
- Search/status/assessment API parameters remaining independent.
- URL round trips preserving selected call, unrelated parameters, Unicode and hash.
- Existing STT, read-only, audio, pagination and hand-labeled-evidence tests unchanged in meaning. Loader-only changes accommodate the new type-safe summary parser.

`frontend/tests/demo-ux-followup.browser.mjs` refuses hosted targets and uses actual local FastAPI/SQLite and a production Next build at 127.0.0.1:8459/:3459. It verifies:

1. Overview's six synthetic calls and explicit real-only coverage.
2. Two confirmed policy-match calls remain Processed; separate assessment filtering works without a document reload.
3. Matching/nonmatching search, processing combinations, empty results, Back/Forward and reload.
4. One no-match call in two supported checks and three not-assessed calls.
5. Direct call URLs and closing/Back/Forward preserve filters without stuck loading.
6. Invalid assessment/processing queries show errors and Reset filters recovers.
7. Public mutations and uploads return403; no upload/delete controls; invalid pagination remains422.
8. No policy edit/disable/remove controls; hallucination example remains explicitly hand-labeled with no live detector claim.
9. Synthetic signed-amount disagreement remains20.0%, actual audio advances after0.6 and repeated seeking works, missing timestamps stay Not scored.
10. Benchmark retains28/28; desktop and 390px mobile filters/Overview do not overflow.
11. A deliberately delayed summary response shows loading, then correct scoped data.
12. Injected API503 and partial summary responses show Overview unavailable rather than fabricated coverage.
13. An injected empty dataset reconciles with zero real/synthetic totals and scoped zero-of-zero coverage.

Successful core journeys use real local responses and generated audio, with normal Chromium autoplay policy. Delay,503, partial-summary and empty-dataset scenarios are explicit fault/fixture injection, not real Render outages or actual customer data. Real-only data tests use authored non-demo IDs in isolated unit stores. Screenshots: `overview-scoped.png`, `mobile-filters.png`, `mobile-overview.png` under `browser-verified/`. Before screenshots and raw responses: `overview-before.png`, `filter-before.png`, `hosted-before.json`. Private keys and generated artifacts remain ignored.

## Second-pass review and remaining issues

The review compared the API/store filter classifications against existing badges, checked pagination and tie ordering, verified `get_run_summary()` arithmetic is unchanged, and reviewed loading/history interactions and new response validation. Read-only/authentication middleware, STT comparison/scoring, synthetic fixture IDs, provider configuration, billing and production were not changed.

- **P0:** No new P0 defect found in this local review; no production-readiness claim.
- **P1:** The repository's existing temporary Chroma advisory exception still requires separate attention before its documented November7 expiry. Dependency files were not changed and dependency audits were not rerun for this UX-only patch. This task does not remediate those findings.
- **P2:** Hosted staging still has the two reported UX issues because these fixes are undeployed. Approval, a reviewed feature commit, fresh exact-commit CI, and an approved backend/frontend staging deployment are needed before hosted acceptance can pass. A frontend-only deployment would silently query an old API that ignores the new assessment parameter.
- **P3:** Assessment filtering scans all search/status candidates in bounded batches to preserve validated-report semantics on both adapters. This is appropriate for six immutable demo calls; it is not an indexed large-dataset or concurrent-writer design. Live PostgreSQL, physical mobile devices, Firefox/Safari and controlled managed cold-start behavior remain unverified. Mobile verification used a Chromium viewport.

**Staging deployment readiness:** local candidate ready for approval; hosted readiness conditional on deployment and verification. No schema migration, metric redefinition, fixture deletion or infrastructure purchase is required. Preserve the public read-only flags and provider-disabled configuration. No commit/push/merge/deploy is authorized by this report.

**STOP: local implementation and verification complete; awaiting user approval.**

Temporary QA servers on 127.0.0.1:3459/:8459 were stopped after verification. No hosted service was stopped or restarted.

## November 3 authorized release handoff

The local-only stop and deployment statements above describe the November 2 verification boundary. The user subsequently approved a scoped feature-branch commit/review, exact-commit CI, and conditional deployment of both components to existing free staging. Main and production remain excluded.

Source review reproduced one additional UI defect before committing: selecting the already-active processing filter set loading without changing effect dependencies, leaving zero visible rows indefinitely. The filter handler now returns when all filter values are unchanged. The browser regression repeats both processing and assessment selections and asserts unchanged results and history length.

Fresh verification on November 3:

- `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest tests/ -q`: **830 passed**, one existing warning, exit 0. Five cases belong to the pre-existing untracked deployment test file, which is excluded from this commit; the committed suite therefore expects 825 cases.
- `cd frontend && npm test`: **74 passed**, 0 failed/skipped, exit 0.
- TypeScript, ESLint and the production Next build: exit 0 after the UI guard change.
- `DEMO_UX_URL=http://127.0.0.1:3459 ... node frontend/tests/demo-ux-followup.browser.mjs`: **13 journeys passed**, no page errors or reference submissions, exit 0 after the guard change.
- One initial browser run failed its fixed 650ms playback-progress assertion. Instrumentation showed correct seeking to 0.6 and subsequent playback; the test now waits up to 10 seconds for actual progress beyond 1.05 instead of assuming audio startup latency. Its progress threshold remains unchanged. The complete suite then passed.

Fresh private evidence is in ignored `.gstack/ux-staging-release/`: `local-backend-tests.log`, `frontend-tests-final.log`, `types-final.log`, `eslint-final.log`, `local-browser-final.log`, and `local-browser/results.json`. The repeated-filter reproduction and audio diagnostic are retained there. The prior fingerprint is historical; Git's scoped commit will identify the release candidate. Unrelated deployment documentation/configuration/test changes remain excluded.

Hosted acceptance and CI are not claimed by these local results. The release handoff must record the exact new commit and actual subsequent outcomes separately. The existing Chroma exception still expires before November 7 UTC; this patch does not fix those vulnerabilities.
