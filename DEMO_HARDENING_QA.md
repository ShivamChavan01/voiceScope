# Synthetic demo hardening and QA — November 1, 2026

**November 2 handoff:** The user has now authorized committing and pushing this reviewed patch to the feature branch for independent agent testing. Deployment and merging remain unauthorized. The verification state below records the pre-commit snapshot; use the commit containing this report to identify the pushed patch. Five tests in the 810-test local run belong to the preserved, pre-existing untracked `tests/test_deployment_config.py`; that unrelated file and the Railway edits are intentionally outside this commit. Do not present the local count as an exact-commit CI result.

**DEMO READINESS: CONDITIONAL GO for the locally verified candidate. Existing hosted demo: FAIL; fixes are not deployed.** No commit, push, merge, managed deployment, production/Neon operation, billing change or paid provider call was made in this task.

## Exact repository state

- Branch: `feat/voicescope-reliability-stt-demo`.
- Starting and final HEAD, also verified on the remote feature branch: `3ba2573b98a78b790c88e8787bc76a94f7453cc6`.
- Remote main remains `f9d459c75e7152e370afed838bc547dde9d0a2d5`.
- All fixes below are **uncommitted and unstaged**. Old green CI does not cover them.
- Existing modifications to `FREE_STAGING_VERIFICATION.md` and `railway.toml`, and pre-existing untracked `HOSTED_RELEASE_VERIFICATION.md`, `docs/staging-acceptance.md` and `tests/test_deployment_config.py`, were preserved. Their presence contributes to local test counts; they are not newly implemented fixes from this task.
- Final code/config fingerprint: `9c805f57f35f62d795f388a9ca26779faa655faade8e5384f3ed22d2f11d85bf`. SHA-256 over sorted Git-visible code/config paths, NUL, bytes, NUL; Markdown excluded. It includes existing visible changes and tests. Runtime files matched the isolated tested snapshot. Private credentials, logs, recordings and databases were excluded by Git ignores and did not match the visible-file scan.

## Architecture and scope

The existing Next.js/React frontend calls a same-origin server proxy, which supplies the backend key server-side. FastAPI handles the deterministic checks and persisted runs. The synthetic environment uses isolated local SQLite stores and private STT artifacts, with no DATABASE_URL or provider credentials. Chroma remains an embedded, separately initialized subsystem; no vector-store or transcription architecture was replaced. Tests used generated speech and authored transcripts only.

## Reproductions, causes and fixes

| Issue | Reproduction and root cause | Local result |
| --- | --- | --- |
| P1 public mutations | Hosted anonymous DELETE of a deliberately nonexistent demo ID reached the handler (404), and an empty policy POST reached validation (422), without modifying a real row. Isolated regressions proved actual deletion and policy access were allowed. `middleware/staging_demo.py:14` previously filtered some POSTs but allowed policy POSTs and all DELETE/PUT/PATCH operations. | **PASS.** Both backend synthetic/public flags enable a read-only middleware boundary: all POST/PUT/PATCH/DELETE return 403, even with the valid shared backend key. Only explicit demo read paths remain available; configuration paths are denied. API-key authentication itself remains required on the backend. Server-supplied UI context hides uploads, deletion, seeding, editing and STT setup. Private-mode tests still pass. |
| Audio seeking | Real hosted trace: currentTime 0.6 with readyState 0, then currentTime 0 when metadata arrived. The old handler set time and called play immediately. Both origin and proxy lacked usable range handling; hosted Range returned 200 with no Accept-Ranges. | **PASS.** `frontend/src/lib/audio-seek.ts:2` waits for metadata and actual seek completion, then plays. New requests cancel pending ones; unmount/source changes cancel listeners. Invalid/out-of-duration times, media errors and timeouts surface errors. `api/stt_routes.py:100` supports single byte ranges, suffix/open-ended requests, 206/416 and If-Range fallback. The frontend forwards range headers and preserves response range metadata. |
| Pagination | Hosted `/runs?limit=1&offset=-1` returned 200 and offset -1; SQLite treats a negative offset as zero. A separate isolated test also reproduced an integer-overflow error for an enormous offset. | **PASS.** `api/routes.py:430` bounds limits to 1–200 and offsets to 0–2,147,483,647, returning 422 before storage. History, incidents, QA result lists and extraction result lists use the same limit range. |
| Drawer URL/history | Hosted close left `call=demo-staging-stt` in the URL. The component read the query once at mount, opened rows through state alone, and closed state without navigation. | **PASS.** `frontend/src/app/runs/page.tsx` and `frontend/src/lib/call-navigation.ts:1` synchronize opening/closing and popstate, retain unrelated query/hash, preserve reload selection and show invalid-ID errors. Request counters prevent stale detail responses from replacing a newer selection. |
| Duplicate scenarios | Six canonical `demo-staging-*` records come from startup; the existing demo button separately wrote three `demo-review-*` records containing the same authored conversations. Repeating either fixed-ID seed was not itself generating random-ID copies. | **PASS.** In synthetic staging, the older seed route now reuses the canonical six IDs (`api/routes.py:258`). Public callers cannot seed. Existing copies and real/user records are not deleted; the UI explicitly identifies earlier duplicate samples. Startup refuses a store containing non-synthetic calls before writing fixtures (`core/staging_demo.py:86`). Fresh storage restores six canonical examples; existing safe legacy copies remain visible. |
| Three detector misses | The local baseline and independently fetched hosted benchmark both showed 25/28, with `challenge-assure`, `challenge-lead`, `challenge-returned` missed. Existing grammar lacked assurance, team-lead/let-you-speak patterns and returned-money completion phrasing. | **PASS within bounded scope.** `core/reliability.py:106` adds these explicit forms while retaining quote, report, conditional, negation, speaker and financial-transfer guards. Returned money creates an **unverified claim / needs review / missing action_result**, never a confirmed completed refund or a confirmed tool failure. |
| Additional retry race | Isolated browser reproduction: an old, delayed Retry response overwrote newer search results, displaying nine rows instead of the matching one. Only effect-driven requests had stale-response protection. | **PASS.** A shared list request counter now fences effects and retries, including their loading/error transitions. Browser regression verifies the matching row remains after the older response arrives. |
| Additional malformed/timeout handling | A new regression proved `{}`/null/malformed lists and empty details were accepted by typed-but-unvalidated fetch calls. Call reads also had no deadline. | **PASS.** `frontend/src/lib/api.ts:140` validates list/detail shape and identity, encodes IDs, preserves explicit zero query parameters, and applies a 30-second deadline to call reads. Errors show retry states. Provider operations were not given a new timeout or pipeline change. |

Public mode requires the backend flags as well as the frontend configuration. Hiding buttons alone is not a security fix. `render.staging.yaml` now declares the backend public flag locally, and `docs/public-synthetic-demo.md` documents the boundary and deployment prerequisites. No hosted environment was edited.

## Regression coverage

Backend additions: `tests/test_free_staging.py` covers all four mutation methods, state preservation, direct authenticated API rejection, private configuration denial, normal private staging, canonical seed idempotency, bounded/default/invalid/huge pagination and refusal of real records without deletion. `tests/test_stt_review_api.py` covers valid and invalid ranges. `tests/test_reliability.py` adds assurance, team-lead refusal and completion-claim positives with adversarial negatives. The existing benchmark tests now assert the improved exact result and still deliberately inject incorrect labels/detectors to prove failures are reported. No expected dataset labels or thresholds were weakened; the authored dataset was not changed.

Frontend additions: `audio-seek.test.mjs`, `call-navigation.test.mjs`, `demo-access.test.mjs`, and extensions to `stt-proxy.test.mjs` and `upload-stream.test.mjs`. They cover readiness, cancellation, rapid/repeated/zero/near-end seeking, invalid/missing times, errors/timeouts, range proxying, URL encoding/query preservation, explicit read-only context, malformed responses and call read deadlines.

`frontend/tests/demo-hardening.browser.mjs` is an opt-in **local-only** regression suite. It refuses hosted URLs because its mutation tests must never operate on shared deployment data.

## Executed verification

Private evidence is under ignored `.gstack/demo-hardening/`. The API and frontend ran as actual isolated services at 127.0.0.1:8359 and :3359. Browser acceptance used a production-mode Next build, actual SQLite fixture storage, real generated WAV playback and Chromium desktop/mobile viewports. No external provider was contacted.

Environment: Python 3.12.3, Node 24.17.0, Chrome 156.0.8078.79, Docker 29.9.2; the Dockerfile uses Python 3.11. The final compiled static files were additionally scanned for the local backend key; no match was found (`client-secret-scan.json`).

| Command/check | Status | Actual result |
| --- | --- | --- |
| Baseline `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= .venv/bin/python -m pytest tests/ -q` | **PASS** | 744 passed, one existing Starlette/httpx deprecation. |
| Final same full backend command | **PASS** | **810 passed**, exit 0; `backend-verified.log`. |
| `cd frontend && npm test` | **PASS** | **69 passed**, exit 0; `frontend-verified-final.log`. |
| `npx tsc --noEmit` | **PASS** | No errors; `types-verified-final.log`. |
| `npm run lint` | **PASS** | No errors; `eslint-verified-final.log`. |
| `.venv/bin/python -m ruff check .` | **PASS** | All checks passed; `ruff-final.log`. |
| `.venv/bin/python -m mypy . --ignore-missing-imports --exclude sdk/` | **PASS** | 141 source files; existing notes about unchecked untyped bodies; `mypy-final.log`. |
| `npm run build` in isolated final source/Preview environment | **PASS** | Exit 0; `build-final.log`, `build-final.exit`, `rebuild-verified.log`. |
| Local browser command below | **PASS** | **18 journeys**, zero page errors, normal Chromium autoplay policy; `browser-acceptance.log`. |
| `python scripts/run_reliability_benchmark.py --json ...` | **PASS** | **28/28** exact cases; supported 24/24, challenge 4/4; TP13 FP0 FN0. Authored regression evidence only. |
| `docker build -t voicescope-demo-hardening:local .` | **PASS** | Exit 0, existing Dockerfile; `docker-build.log`. |
| Fresh container smoke | **PASS** | UID999, writable DATA_DIR, PORT10000, no mounts, 512 MiB cap, six fixtures, authenticated reads, public mutations/config denied, range206, signed disagreement and Not scored. Health/check completion 8.32 seconds; no observed OOM. |
| Raw requirements `pip_audit -r requirements.txt --format json --progress-spinner off --timeout 20` | **FAIL** | Exit 1: five Chroma records/four unique advisory IDs. Not a clean raw audit. |
| `python -m tools.dependency_audit` in existing audit environment | **PASS with existing exception** | Exit 0; four version-bound Chroma IDs assessed below. No ignore added. |
| Complete installed Docker inventory through `tools.dependency_audit --inventory ...` | **PASS with existing exception** | Exit 0, same Chroma scope; `image-audit.log`. |
| `npm audit --json` | **FAIL** | Exit 1, **19 moderate + 2 low** existing advisories; no high/critical. |
| `npm audit --audit-level=high` | **PASS** | Exit 0; no dependency changes or audit overrides. |
| Git-visible private-secret/media/database/log scan | **PASS** | No known staging secret matches or raw media/database/log artifacts. Authored packaged audio JSON is intentional; runtime snapshot matches. |
| `git diff --check` | **PASS** | No whitespace errors. |
| New exact-commit GitHub CI | **NOT TESTED** | No new commit/push, by instruction. |
| Hosted verification of the new code | **BLOCKED** | Requires later explicit approval to push/configure/redeploy staging. |

Browser invocation (with local installed browser/tool paths supplied):

```sh
DEMO_QA_URL=http://127.0.0.1:3359 \
DEMO_QA_EVIDENCE=/path/to/ignored/evidence \
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs \
CHROME_PATH=/usr/bin/google-chrome \
node frontend/tests/demo-hardening.browser.mjs
```

The 18 journeys exercise overview, read-only policy/settings display, explicit violation/compliant/escalation/hand-labeled examples, transcript evidence, missing audio, public API mutation rejection, pagination, search/status empty states, drawer opening/closing/Back/Forward/reload/invalid IDs, stale detail and retry responses, all five report tabs, audio before metadata/paused/playing/repeated/ended, rapid different timestamps, zero/near-end/invalid times, missing timestamps, mobile layout, keyboard focus, benchmark, service failure, malformed success, failed audio and an accelerated timeout.

Measured actual audio positions: rapid latest target **0.2 → 0.2**, zero **0 → 0**, near end **3.49873 → 3.49873** seconds. The metadata test asserts initial readyState0, delays the actual recording response, then checks playback remains advanced after metadata rather than checking only a queued currentTime. No autoplay override was used in final acceptance. The standalone media harness uses the actual seeker implementation with an actual audio element; evidence-button scenarios use the rendered React UI. HTTP 206/range headers are asserted.

Fault scenarios deliberately inject a 503, malformed JSON object, audio500, or delay into otherwise real local requests. Timeout tests accelerate the native deadline; they are not a wall-clock measurement of 30 seconds. Successful core journeys use the actual local API/storage/audio. Screenshots: `browser-acceptance/audio-evidence.png` and `mobile.png`; full observations in `browser-acceptance/results.json`. Network/console failures intentionally induced by fault cases are not labeled clean network traffic.

## Failures retained during development

- New backend regressions initially produced **21 failures**: mutations, pagination, duplicate seed path and ignored audio ranges.
- A separate real-record startup rejection test failed before its guard, and an oversized offset reproduced SQLite overflow before its bound.
- Detector regressions initially had **five failures** across the three missing forms/variants. After improvements, three old benchmark assertions failed because they required the historical misses; they were strengthened to exact new counts while preserving injected-failure tests.
- The retry race browser failed with nine rows instead of one. A malformed API regression failed because the old code did not reject invalid data.
- Intermediate frontend checks caught a JSX brace mistake and a data-URL test-harness React import issue; both were corrected. A prior hosted inspection helper waited for the wrong close-button label, then used Escape. None of those intermediate runs is counted as a pass.
- Final required local suites have no application failures. Raw dependency audits still have the explicitly recorded findings.

## Independent existing-hosted observations

Target: `https://voicescope-staging-demo-git-fea-26f564-shivamchavan01s-projects.vercel.app/`.

**FAIL:** negative offset accepted and echoed; drawer query remains after close; anonymous mutation requests reach handlers; recording seek resets during metadata loading; audio range returns 200 with no Accept-Ranges; benchmark remains **25/28** with the three reported challenge misses. Nine synthetic calls are present. Hosted inspection used reads and invalid/nonexistent mutation targets only; it did not create/delete a real shared record, seed, restart, change settings or call a provider. Evidence: `hosted-repro.json`, `hosted-audio.png`, `hosted-benchmark.json`, `hosted-range.json`.

These observations describe the old deployment, not the new local code. It is **not ready to validate the fixes** until the candidate is approved, pushed, passes its own CI, and both staging components are updated. The backend must receive its public read-only flag; a frontend-only deployment does not enforce the server boundary. No production release is needed or authorized.

## Security findings and limits

The remaining Python exception is for pinned ChromaDB1.5.9: `PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814`, `PYSEC-2026-3815`, expiring **before November 7, 2026 UTC**. It is an assessed temporary exception, not a security fix. No new advisory IDs were found in this audit. Public demo routes deny knowledge/configuration access; no Chroma server or paid provider was enabled. Existing npm moderate/low advisories remain. See `docs/chroma-advisory-assessment.md` for the existing bounded assessment.

This remains a public fixture environment, not tenant isolation or authenticated visitor access. It requires its own ephemeral DATA_DIR, no external database and no real data/provider credentials. Non-synthetic calls cause startup to fail closed without deletion. Real/private staging behavior remains available when backend public mode is absent. Keys stay server-side; no human-reference transcript, tool execution or speaker identity was invented.

**NOT TESTED:** new hosted deployment/configuration, new GitHub CI, managed-host resource/restart/idle behavior in this task, long-term expiry by waiting 24 hours, Firefox/Safari, physical mobile devices, comprehensive accessibility certification, sustained/concurrent-user load, real Bolna/Deepgram integration or held-out detector accuracy. The local container's one CPU and sampled test window do not establish Render Free startup/capacity. Existing deterministic/unit tests cover WER, signed amounts, speaker/time alignment, invalid/long intervals, absence/expiry and uncertainty; this is not a scored real-call acceptance result.

Free local storage is still ephemeral. Canonical startup restores six scenarios; old duplicate records are preserved if storage survives, but a Free service replacement may lose old duplicate URLs or any prior state. Synthetic STT artifacts expire after 24 hours and are restored by startup; anonymous reseeding is intentionally forbidden. No backup/durability claim is made.

## Files in this fix

Backend/config: `api/routes.py`, `api/stt_routes.py`, `core/reliability.py`, `core/staging.py`, `core/staging_demo.py`, `middleware/staging_demo.py`, `render.staging.yaml`.

Frontend: `frontend/src/app/{layout,page,runs/page,settings/page}.tsx`, `frontend/src/app/api/[...path]/route.ts`, `frontend/src/components/{demo-access,policy-rules,stt-review}.tsx`, `frontend/src/lib/{api,operator-auth,audio-seek,call-navigation}.ts`.

Tests: `tests/test_free_staging.py`, `tests/test_stt_review_api.py`, `tests/test_reliability.py`, `tests/test_reliability_benchmark.py`, and frontend tests named above. Documentation: this report and `docs/public-synthetic-demo.md`. All pre-existing unrelated changes remain unstaged and preserved.

**Local verification complete. Feature commit/push authorized November 2; staging deployment still awaits separate approval.**
