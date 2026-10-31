# Independent release-candidate QA — October 31, 2026

**Fix follow-up:** The reproduced defects below were subsequently repaired and retested. See [RELEASE_FIXES.md](RELEASE_FIXES.md) for the current local artifact, 715 backend/56 frontend results, browser/container verification, and remaining release limits. This report preserves the original failing QA evidence; it does not describe the post-fix artifact.

## Release decision

**NO-GO for the current release candidate.** Existing automated suites pass, but independent adversarial checks and a production-mode browser reproduce release-blocking behavior. This was a verification-only pass: no application fixes, commits, pushes, merges, deployments, credential changes, or production data mutations were made.

| Decision | Result | Reason |
| --- | --- | --- |
| A. Commit as the approved release candidate | **NO-GO** | Unresolved correctness, browser, and privacy findings below. This does not prohibit an explicitly requested WIP checkpoint. |
| B. Push as the reviewed feature release | **NO-GO** | Fix/review the reproduced blockers first; no push was authorized or executed. |
| C. Merge into main | **NO-GO** | Current candidate is dirty and has no exact-commit CI result; latest remote CI audit failed and Docker was skipped. |
| D. Deploy production | **NO-GO** | Code blockers plus missing operator environment configuration and unverified backend deployment, backup, and rollback prerequisites. |
| E. Complete private Bolna buildathon demo | **NO-GO for full acceptance** | At the documented IPv4 loopback URL, legitimate mutations and fonts fail. Evaluation findings also have confirmed errors. A restricted, honest, cached playback demonstration at `localhost` is possible, but is not a release sign-off or a scored STT accuracy demonstration. |

## 1. Exact tested state and preservation

- Branch: `feat/voicescope-reliability-stt-demo`.
- Local HEAD and freshly queried remote feature HEAD: `299666b7df94bacbd046f9e06b3e68c9b15d128b`.
- Local main and freshly queried remote main: `f9d459c75e7152e370afed838bc547dde9d0a2d5`.
- The candidate includes existing uncommitted implementation changes. Testing HEAD alone would not identify the tested artifact.
- Starting Git-visible inventory: **238 files**. Diff against main: **126 tracked changed paths plus 14 new files**, recorded in `.gstack/independent-qa/changed-files.txt`.
- Starting short status contained **50 entries**, including the collapsed untracked `tools/` directory. The index was empty; nothing was staged by QA.
- Runtime/source fingerprint: **`3e327c0315a18cda250f99152c4f30363235a24f0e3a9bed75f099b30a947b4d`**. Definition: SHA-256 over sorted Git-visible, non-Markdown regular-file relative paths, NUL, file bytes, NUL. Ignored files are excluded.
- An isolated snapshot, including the existing uncommitted files, was tested under `.gstack/independent-qa/source`. It contains no project `.env` file. Original files were independently hashed and subsequently checked for changes.
- The sole new Git-visible artifact from this pass is this report. Reproduction tests, logs, configuration, copied databases, screenshots, and real-call evidence remain under ignored `.gstack/independent-qa/` with a private parent directory. No private recording or credential was added to Git.

The complete tracked patch and an inventory with per-file hashes were captured. Review concentrated on authentication, proxy normalization, webhook lifecycle, scoring, STT provenance, persistence, dependency policy, deployment boundaries, and associated UI/tests. Automated checks cover the wider changed tree; this is not a claim of formal verification or exhaustive security coverage of every possible input.

## 2. Test environment

Linux; host Python **3.12.3**, container Python **3.11.18**, Node **24.17.0**, npm **11.13.0**, Docker **29.9.2**, pytest **9.1.0**, mypy **2.1.0**, Ruff **0.15.17**, Next.js **16.4.3**, ChromaDB **1.5.9**. Playwright uses the existing private installation and `/usr/bin/google-chrome`; no browser dependency was added to the application.

Independent production-mode servers used backend `127.0.0.1:8089`, frontend `127.0.0.1:3089`, and access-test variants on 3090–3092. Original review services were preserved. SQLite copies used the online backup API from read-only source connections. The isolated backend has no live transcription/LLM credentials; it can serve cached authorized evidence without silently creating a provider submission.

Docker image built independently: `voicescope-independent-qa:local`, image ID **`sha256:9e2286dcf7758626f298ca209313f5534427974094878f53043a9fe4fb312469`**. A fresh, synthetic-only volume `voicescope-independent-qa-data` was used for container acceptance.

## 3. Commands, results, and counts

All paths below are relative to the repository unless a working directory is specified. Evidence directory is `.gstack/independent-qa/`. Exit codes are actual observed process results.

| Check / command | Exit | Actual result |
| --- | --- | --- |
| In snapshot: `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= /mnt/nvme0n1p10/voicescope/.venv/bin/python -m pytest -q` | 0 | **677 passed**, 69.35 seconds; one Starlette/httpx deprecation warning. `backend.log`. |
| In `frontend`: `npm test` | 0 | **55 passed**, no failed, cancelled, skipped, or todo tests. `frontend.log`. |
| `.venv/bin/python -m ruff check .` | 0 | All configured checks pass. `ruff.log`. |
| `.venv/bin/python -m mypy . --ignore-missing-imports --exclude sdk/` | 0 | No issues in 134 source files. Notes explicitly say untyped function bodies are not checked. `mypy.log`. |
| In `frontend`: `npx tsc --noEmit` | 0 | Pass. `typescript.log`. |
| In `frontend`: `npm run lint` | 0 | ESLint passes. `eslint.log`. |
| In snapshot `frontend`: `npm run build` | 0 | Optimized production build succeeds; build ID `vQ3TA4eeQ2dUz1SBkgbHk`. `build.log`. |
| Fresh isolated package/lockfile directory: `npm ci`, then `npm ls --depth=0` | 0 / 0 | 525 packages installed; lockfile resolves Next 16.4.3 and React 19.2.4. Audit warnings remain. `npm-ci.log`, `npm-ls.log`. |
| `.venv/bin/python scripts/run_benchmark.py --min-truth 0.7` | 0 | 10 fixtures; heuristic score 0.8500. Hallucination accuracy explicitly **not measured**. `benchmark.log`. |
| `.venv/bin/python scripts/run_reliability_benchmark.py --json .gstack/independent-qa/policy-benchmark.json` | **1** | **25/28** exact cases; supported 24/24, challenge 1/4; TP 10, FP 0, FN 3; default required agreement not met. |
| Audit-environment Python: `-m pip_audit -r requirements.txt --format json --progress-spinner off --timeout 20` | **1** | Five Chroma records, four unique advisory IDs; not a clean raw audit. `requirements-audit.json`. |
| `.gstack/merge-readiness/audit-env/bin/python -m tools.dependency_audit` | 0 | Passes **with four explicit temporary Chroma exceptions**, not vulnerability fixes. `audit-policy.log`. |
| In `frontend`: `npm audit --json` | **1** | **21 findings: 19 moderate, 2 low; 0 high, 0 critical**. |
| In `frontend`: `npm audit --audit-level=high` | 0 | Threshold passes; the 21 lower-severity findings remain. |
| `docker build -t voicescope-independent-qa:local .` | 0 | Independently built current candidate. `docker-build.log`. |
| Full backend suite inside Python 3.11 image, then configured mypy and Ruff | 0 | **677 passed**, 85.73 seconds; mypy 133 source files and Ruff pass. `container-tests.log`. |
| `.venv/bin/python .gstack/independent-qa/container-run.py` | 0 | Fresh volume, replacement, restart, private data modes, expiry, receipt persistence, missing-provider terminal state. |
| `.venv/bin/python .gstack/independent-qa/container-boundary.py` | 0 | 11 private context canaries excluded; 3 required fixtures retained; embedded Rust transport enforced. |
| Full pinned installed-image inventory: `pip_audit -r .gstack/independent-qa/image-requirements.txt --no-deps --disable-pip --format json --progress-spinner off --timeout 20` | **1** | **20 records in 3 packages**, including pip/setuptools not covered by the requirements-only gate. See security assessment. |
| `.venv/bin/python .gstack/independent-qa/security-probe.py`, final corrected fixture | 0 | **59 HTTP checks pass**, plus client-bundle credential scan. Does not include the separate failing legitimate-origin regression. |
| `.venv/bin/python -m pytest -q .gstack/independent-qa/probes/test_webhook_independent.py` with isolated environment | 0 | **7 independent ASGI/real-SQLite tests pass**, including explicitly observed duplicate-report limitation. Provider processing is a controlled fake. |
| Private adversarial Python probes, detailed below | **1** each | **8 failing assertions** across scoring, findings, privacy, and knowledge refresh. They remain failing; no assertions were weakened. |
| `node --experimental-strip-types --test .gstack/independent-qa/probes/loopback.test.mjs` | **1** | One failing same-origin regression using the real NextRequest class. |
| `node tests/private-access.browser.mjs`, isolated production frontend after readiness | 0 | Auth, assets, cross-origin rejection, disabled encoded STT routes. Initial attempt failed 502 before backend was ready; retained separately. |
| `node tests/calls-ui.browser.mjs` | 0 | Five-tab UI, keyboard/focus, error/retry and upload UI checks; **API responses are mocked**. |
| `node tests/stt-demo.browser.mjs` | 0 | Actual cached authorized audio playback, reference timestamp seeking, reload, mobile overflow; no new reference POST. Expiry response is controlled/mocked. |
| `node .gstack/independent-qa/extended.browser.mjs` | **1** | Real frontend/API/SQLite journeys; policy saving fails at IPv4 loopback. Screenshots also expose actual persisted scoring defects. |
| `node .gstack/independent-qa/origin.browser.mjs` | **1** | Same-origin policy POST and both Geist fonts return 403. |
| `node .gstack/independent-qa/policy-localhost.browser.mjs` | 0 | Actual policy create/edit/disable/enable/delete/reload and genuine missing-provider SSE terminal error work at `localhost`. Workaround only. |
| `.venv/bin/python .gstack/independent-qa/real-acceptance.py` | 0 | Fresh authorized Bolna execution and recording read; cached reference, durable replay and report checks pass. No fresh Deepgram transcription. |
| `git diff --check`; configured-secret and private-evidence scan | 0 / no matches | Original visible files unchanged; no staged files; no detected credential/private-media additions. |
| `gh run list`, `gh run view 41174064636 --json jobs`, `git ls-remote origin ...` | 0 | Current remote state independently checked. Latest CI remains failed, Docker skipped. |
| `CI=1 vercel --scope shivamchavan01s-projects inspect voice-scope.vercel.app` | 0 | Read-only production frontend metadata available; not an application/rollback acceptance test. |

Container full-suite command:

```sh
docker run --rm --name voicescope-independent-qa-tests \
  --env PYTHON_DOTENV_DISABLED=1 --env DATABASE_URL= \
  --env PYTHONPATH=/tmp/devtools:/app \
  --mount type=bind,source="$PWD/tests",target=/app/tests,readonly \
  --entrypoint sh voicescope-independent-qa:local -c '
    python -m pip install --quiet --target /tmp/devtools \
      pytest==9.1.0 pytest-asyncio pytest-cov mypy==2.1.0 ruff==0.15.17 &&
    python -m pytest -q &&
    python -m mypy . --ignore-missing-imports --exclude sdk/ &&
    python -m ruff check .'
```

The initial raw `pip_audit` without `-r` scanned the audit tool's environment, finding old pip advisories. It was not treated as the application audit; the corrected requirements and image inventory audits above were run separately. An early independent webhook fixture omitted `telephony_data`, so it was classified as generic and rejected with 403; a wait without a timeout was interrupted (exit 2). Corrected, Bolna-shaped bounded tests pass. The initial oversized-request probe was below the actual 2 MiB limit; the corrected 2.2 MB request returns 413. These setup corrections did not change application code or lower expected protection.

## 4. Confirmed defects

Severity here describes product/release impact, not a claimed CVSS rating. Findings explicitly identify inherited behavior where established.

### F01 — High: valid IPv4-loopback browser requests rejected as cross-origin

- **Location:** `frontend/src/lib/operator-auth.ts:17`, `:25`; invoked by `frontend/src/proxy.ts:5` and the API proxy.
- **Reproduction:** Open the isolated production frontend at `http://127.0.0.1:3089/settings` with valid Basic credentials; add a supported policy. The browser sends `Origin: http://127.0.0.1:3089`. Independently, construct the same POST using the installed NextRequest class and call `operatorAccess`.
- **Expected:** Valid same-origin authenticated requests succeed; actual attacker origins stay forbidden.
- **Actual:** Policy save returns **403**, with “Cross-origin access is forbidden.” Font GETs with the same Origin also return 403. Uploads at this origin are rejected before provider processing. With `localhost` as both browser host and Origin, policy mutations succeed.
- **Root cause:** Next's installed `NextURL` normalizes loopback addresses to `localhost` (`next/dist/server/web/next-url.js:15`). The guard compares that normalized request origin to the browser's literal IPv4 Origin. Its existing unit tests use plain Request objects and miss this framework behavior.
- **Impact:** The documented private demo has broken write workflows and fallback fonts even though all three earlier browser suites can pass. Their coverage did not assert a successful real same-origin mutation or font fetch.
- **Evidence:** `probes/loopback.test.mjs`, `loopback-regression.log`, `same-origin-results.json`, `origin-browser.json`, `screenshots/failure-7.png`; localhost countercheck in `policy-localhost-browser.json`.
- **Correction:** Validate the externally intended origin without losing framework-normalized host information. Preserve strict cross-origin rejection and test real NextRequest, production browser POSTs, fonts, non-loopback HTTPS, and forwarded-host trust. Do not simply disable the Origin check.

### F02 — High: unrelated financial transfer becomes a confirmed escalation violation

- **Location:** `core/reliability.py:175`, especially the fallback at `:187`; consumed at `:283`.
- **Reproduction:** Enabled supervisor-request rule; explicit customer says “Please transfer me to a supervisor.” Agent says “I cannot transfer money between accounts.”
- **Expected:** This statement does not establish refusal to transfer the caller. Preserve uncertainty about the unresolved request.
- **Actual:** A **confirmed, high-severity policy violation**, “Requested escalation was explicitly refused,” is emitted and shown in the actual call-detail UI.
- **Root cause:** The refusal regex accepts “I cannot transfer”; the target check only rejects a non-human target after “to …”. An explicit different object, “money,” reaches the unconditional true fallback.
- **Impact:** A financially unrelated sentence can incorrectly accuse the agent of a confirmed company-policy violation.
- **Evidence:** `probes/test_adversarial.py::test_money_transfer_is_not_a_refusal_to_transfer_the_caller`; `screenshots/defect-escalation-false-positive.png`.
- **Correction:** Require the refusal to refer to the caller's requested human escalation; reject explicit unrelated transfer objects and test intervening requests/negation/scope.

### F03 — High: meaning-changing signed amounts produce no STT finding

- **Location:** `core/stt_quality.py:114`, `:145`, and comparison finding creation.
- **Reproduction:** Same speaker/time/hash and caller-only scope. Bolna: “The balance is 100 dollars.” Reference: “The balance is -100 dollars.” Exercise both an automatic reference and a deliberately labeled synthetic human-reference fixture.
- **Expected:** Detect the meaning-changing amount discrepancy; show review status for automatic evidence and the appropriate human-reference result. Any WER normalization convention must not suppress the separate semantic finding.
- **Actual:** **0.0** metric, no substitutions/deletions/insertions, **no findings** in both modes. The actual browser shows 0.0% alongside texts with opposite signed amounts.
- **Root cause:** Tokenization discards the minus sign; both edit comparison and meaning-change detection reuse these tokens. The changed-number set is empty.
- **Impact:** A debt versus credit/balance sign error is invisible. This is not proof that the real call is inaccurate; the reproduction is synthetic.
- **Evidence:** Two parameterized failures in `test_negative_amount_sign_cannot_disappear_from_transcript_comparison`; `screenshots/defect-negative-amount-zero-disagreement.png`.
- **Correction:** Preserve signed numeric meaning in semantic comparison, with an explicit documented tokenization contract. Cover minus, Unicode minus, currency signs, decimal amounts, and written negative amounts. Do not hide the issue with score clamping.

### F04 — Medium: numeric support also conflates opposite signed values

- **Location:** `core/facts.py:34` and `FactExtractor.verify`'s normalized value set.
- **Reproduction:** Transcript “The balance is -100 dollars.” Analysis finding “The balance is 100 dollars.”
- **Expected:** The positive value is unsupported by the observed negative value.
- **Actual:** Accuracy **1.0**, one supported claimed value, no unsupported claim.
- **Root cause:** `NUMBER_PATTERN` omits numeric signs before Decimal normalization. The unsigned pattern already exists on main; the current scoring correction does not resolve this case.
- **Impact:** Numeric support can appear perfect for a meaning-changing financial error. The metric remains a bounded support heuristic, not proof of semantic correctness.
- **Evidence:** `probes/test_additional.py::test_numeric_support_preserves_negative_sign`.
- **Correction:** Define signed-value normalization explicitly and test both directions, currency formatting, and unsupported values without turning absence into a confirmed voice-agent hallucination.

### F05 — Medium: negation in another clause suppresses a literal forbidden guarantee

- **Location:** `core/reliability.py:101`, `:132`, `:136`.
- **Reproduction:** Active no-same-day-refund-guarantee rule; explicitly labeled agent: “I guarantee your refund today, not tomorrow.”
- **Expected:** The explicit same-day guarantee matches the configured prohibition.
- **Actual:** No policy finding.
- **Root cause:** Sentence-wide negation filtering treats any “not” as negating the guarantee, ignoring its clause/target.
- **Impact:** An ordinary affirmative promise with an unrelated negative qualification bypasses the supported check. No-match wording is appropriately limited in the UI, but the missed detection remains real.
- **Evidence:** `probes/test_additional.py::test_negation_in_other_clause_does_not_erase_explicit_guarantee`.
- **Correction:** Scope negation to the claim instead of the whole sentence; retain the existing tests for actual negations, quotations, questions, and hypotheticals.

### F06 — Medium: malformed persisted STT data is echoed into an error response

- **Location:** `api/stt_routes.py:83`; `core/stt_service.py:121` validates the saved original before its sanitized provider-error block.
- **Reproduction:** Supply a synthetic stored Bolna run whose segment has a speaker and a dictionary instead of text, containing a private canary. Authenticated POST to `/stt-review/reference` with existing provider configuration.
- **Expected:** Sanitized 422/error description; malformed saved transcript fields are not echoed.
- **Actual:** The 422 detail includes the Pydantic `input_value`, including the synthetic private canary.
- **Root cause:** A Pydantic ValidationError is a ValueError; `str(exc)` is returned verbatim. The request-validation sanitizer does not cover validation of already stored data.
- **Impact:** Sensitive fields can enter frontend error display and error-capture tooling. This requires authenticated access and malformed persisted data; **no unauthenticated or cross-company leak was demonstrated**.
- **Evidence:** `probes/test_adversarial.py::test_stt_reference_error_does_not_echo_saved_private_fields`, corrected fixture in `adversarial-second.log`. The first fixture's longer field name was truncated by Pydantic and did not expose the canary; the short-field reproduction does.
- **Correction:** Return a fixed source-validation error and keep detailed input values out of responses/logs. Test stored-source validation separately from provider and request errors.

### F07 — Medium: startup warning still logs raw database exception messages

- **Location:** `main.py:32`; `utils/logger.py:6` only strips structured exception objects.
- **Reproduction:** In an isolated test, make schema initialization raise a RuntimeError containing a synthetic password-shaped canary; capture the configured private logging filter during lifespan startup.
- **Expected:** Log operation/type without the raw credential-shaped payload.
- **Actual:** The warning includes the entire exception message and canary.
- **Root cause:** The exception is interpolated into the message before the logging filter sees it; stripping `record['exception']` cannot remove that text. This startup interpolation is inherited from main.
- **Impact:** A database error containing a DSN/credential can be copied into persistent logs. This is a demonstrated unsafe logging path, **not evidence that an actual production password leaked**.
- **Evidence:** `probes/test_startup_privacy.py`, `startup-privacy.log`.
- **Correction:** Use a static startup message and exception type, consistent with the updated storage/provider handlers; verify both stdout and serialized sinks.

### F08 — Medium: removed reference-knowledge chunks survive reload

- **Location:** `core/knowledge_base.py:59`.
- **Reproduction:** Use real embedded Chroma and a temporary two-paragraph synthetic knowledge file. Initialize the KB; remove the second paragraph and reload. Inspect actual collection documents.
- **Expected:** The retired paragraph is absent from the rebuilt index.
- **Actual:** Collection still has both documents; the retired guidance remains retrievable after a successful reload.
- **Root cause:** Reload upserts current sequential IDs but never removes obsolete higher IDs. This behavior is inherited from main, rather than introduced by the embedded-client wrapper.
- **Impact:** Deleting reference guidance need not remove it from model context. Structured policy-rule storage is separate; this does not prove that a deleted deterministic rule is still applied.
- **Evidence:** `probes/test_knowledge_refresh.py`, `knowledge-refresh.log` using a real Chroma collection.
- **Correction:** Reconcile obsolete index IDs when rebuilding, and test shrinking, editing, deletion, and failed reloads without discarding the last valid index accidentally.

### F09 — Medium release-hardening gap: requirements-only audit omits image tooling advisories

- **Location:** `Dockerfile:1`, `:6`, `:8`, `:15`; `.github/workflows/ci.yml` audit job runs only the requirements-based policy.
- **Reproduction:** Export installed packages from the independently built image and audit the complete pinned inventory with no dependency resolution.
- **Expected:** The release assessment accounts for all shipped Python packages, including installer tooling.
- **Actual:** Requirements scan reports five Chroma records; image scan reports **20 records across ChromaDB 1.5.9, pip 24.0, and setuptools 79.0.1**. The latter two are outside the Chroma exception.
- **Root cause:** Base-image tooling is installed but is not declared in application requirements and therefore is absent from the CI audit inventory.
- **Impact:** The existing security gate cannot be described as an audit of every package in the production image. These installer advisories are not proof of a remotely exploitable VoiceScope route. Several have OS/runtime prerequisites absent here; see below.
- **Evidence:** `image-packages.json`, `image-audit.json`, `image-audit-summary.json`.
- **Correction:** Assess/update the build and runtime toolchain, or remove unnecessary runtime tooling when compatible, then audit the rebuilt image inventory. Do not extend the Chroma waiver to these packages.

## 5. Security boundary and dependency assessment

### Access, recordings, paths, and privacy

The final 59-check HTTP harness verifies unauthenticated pages/assets/private API denial, malformed/invalid Basic credentials, absent and short operator configuration failing closed, backend key requirements, webhook/operator separation, same-site/cross-site iframe rejection, encoded/double-encoded/traversal STT-disabled paths, invalid/nonfinite JSON and IDs, request-size limits, and missing/incorrect webhook secrets. Private responses checked use `Cache-Control: no-store`.

This suite tests hostile-origin rejection; **it does not excuse F01's rejection of a legitimate origin**. Minimum password length is enforced; no claim of password entropy estimation or individual operator identity is made. All operators are trusted within one company. Primary run lookup is global by design, and STT API-key hashing is artifact scoping, not user authorization.

The full existing suite exercises public-IP/DNS pinning, HTTPS-only recording URLs, private IP/redirect rejection, cross-host credential stripping, MIME and size limits, owner-scoped audio, validation/privacy, provider timeouts, and retention. Fresh Bolna retrieval additionally traversed the real hardened downloader. No destructive SSRF requests were sent to production. Exhaustive DNS rebinding, every proxy implementation, and distributed infrastructure boundaries are not proven by these tests.

Configured-secret scan compared nine existing secret/private-evidence values against all 238 starting Git-visible files, with zero matches. A pattern scan found no credential/private-key/signed-recording canaries or files over 5 MB. The production client bundle did not contain the isolated backend key or operator password. This is targeted evidence, not a guarantee against every encoding or historical Git leak. Existing files and the index were preserved.

### Chroma exception: assessed, not patched

- Exact pin **1.5.9** in both dependency declarations; current PyPI metadata also reports 1.5.9 as latest.
- Raw records: `PYSEC-2026-311` twice, `PYSEC-2026-3813`, `PYSEC-2026-3814`, `PYSEC-2026-3815`; no fixed versions supplied.
- Exception accepts only those IDs/version, no known fix, and dates **before 2026-11-07 UTC**. Unknown IDs, versions, skipped dependencies, invalid results, available fixes, and expiry fail its tests.
- Actual image client remains `chromadb.api.rust.RustBindingsAPI` even when a server transport is set in the environment. Server authn/authz providers are absent; initialization adds **zero listening TCP sockets**; no Chroma server routes are mounted. Both production Chroma callers use the wrapper.
- The advisory entry points are absent from the tested embedded-only application configuration. This supports a **local applicability exception**, not a package vulnerability fix or proof of hosted configuration. Do not deploy a separate Chroma server under this assessment.

Official records: [pre-auth model configuration injection](https://osv.dev/vulnerability/PYSEC-2026-311), [collection-update code injection](https://osv.dev/vulnerability/PYSEC-2026-3814), [tenant authorization](https://osv.dev/vulnerability/PYSEC-2026-3813), [SimpleRBAC resource scoping](https://osv.dev/vulnerability/PYSEC-2026-3815), [current package metadata](https://pypi.org/pypi/chromadb/json).

### Additional image findings

| Package | Unique advisory IDs | Fixed versions reported by raw audit | Applicability limits |
| --- | --- | --- | --- |
| pip 24.0 | `PYSEC-2026-1795`, `1796`, `2875`, `2876`, `196`, `3721` (all prefixed `PYSEC-2026-`) | 25.3, 26.0, 26.1, 26.1, 26.1.2, 26.2 respectively; duplicated metadata also names 26.2.0 | Package installation/download boundaries; no API route installs caller-supplied packages. The tar fallback advisory's PEP 706 condition is absent on the tested Python 3.11.18 (`tarfile.data_filter` exists). Other installer paths require their own assessment; no blanket waiver added. |
| setuptools 79.0.1 | `PYSEC-2026-3447`, `GHSA-xmj3-9gf7-h52w` | 83.0.0, 84.1.0 | First is an NFC/NFD exclusion bypass on macOS filesystems; second is a Windows legacy-wheel path escape. Neither OS-specific entry point is demonstrated on this Linux image. Still shipped and reported; not silently ignored. |

There are **12 unique image advisory IDs in 20 raw records**: four Chroma, six pip, two setuptools. The image-inventory command warns that a no-deps audit is not a hash-locked supply-chain verification. It audits the complete exported installed inventory; it is not an OS-package/CVE scan. No OS image scanner was run.

Primary sources: [pip tar fallback conditions](https://osv.dev/vulnerability/PYSEC-2026-1795), [pip encoded-index URL boundary](https://osv.dev/vulnerability/PYSEC-2026-3721), [setuptools macOS exclusion issue](https://osv.dev/vulnerability/PYSEC-2026-3447), [setuptools Windows legacy-wheel issue](https://github.com/advisories/GHSA-xmj3-9gf7-h52w). Full remaining installer descriptions and fixes are retained in the raw audit rather than represented as active HTTP exploits.

### npm findings

Raw audit: **19 moderate and 2 low**. Advisory roots are [minimatch glob amplification](https://github.com/advisories/GHSA-g3hv-75wg-m249) and [deepmerge prototype poisoning](https://github.com/advisories/GHSA-gcqx-w48m-w2h4). No high/critical npm finding was returned; passing the configured high threshold does not remove lower findings.

Affected moderate package nodes: `@eslint-community/eslint-utils`, `@eslint/config-array`, `@eslint/eslintrc`, `@next/eslint-plugin-next`, `@ts-morph/common`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `@typescript-eslint/type-utils`, `@typescript-eslint/typescript-estree`, `@typescript-eslint/utils`, `eslint`, `eslint-config-next`, `eslint-plugin-import`, `eslint-plugin-jsx-a11y`, `eslint-plugin-react`, `minimatch`, `shadcn`, `ts-morph`, `typescript-eslint`. Low nodes: `@shadcn/registry`, `deepmerge`. These are affected dependency-tree nodes, not 21 distinct exploits. Full ranges and direct/transitive status are in `npm-advisory-summary.json`.

## 6. Webhook durability and failure behavior

Independent synthetic ASGI tests use the real SQLite primary store and receipts, with a controlled fake provider pipeline:

1. Concurrent duplicate: one evaluation enters the provider; second returns **409 + Retry-After: 10**; first returns 200 only after persistence; completed replay returns the same acknowledgment without reevaluation.
2. Primary write failure: **503**, no saved run, receipt released for retry.
3. Missing readback: **503**, receipt not completed.
4. Provider timeout: **500**, no saved run, claim released.
5. Task cancellation: claim released; cancellation is not acknowledged as success.
6. Partial result: acknowledged as **partial**, after the partial report is persisted; not presented as successful validation.
7. Receipt-write failure after report persistence: first returns **500**; retry evaluates again, creates a second report, then succeeds. **Two provider evaluations and two reports were observed.** This deliberately passing characterization test documents a limitation, not exactly-once success.

The separate transactions and finite lease provide **at-least-once processing with deduplication of completed receipts**, not exactly-once provider work. Stale-worker fencing is tested at the receipt layer, but there is no provider-side idempotency key, heartbeat, or durable background queue. A long-lived worker can overlap a reclaimed lease. Multiple replicas with independent data directories cannot coordinate. Post-persistence failure or interruption may repeat cost/work; callers must retry non-2xx responses. No automatic backfill/recovery guarantee is claimed.

Receipt restart persistence was verified in a real restarted container; primary reports survived actual replacement with the same named volume. Hard OS worker termination at every possible instruction, network partitions, independent-host replicas, and actual Bolna retry scheduling were **not** exercised. Task cancellation and receipt expiry tests do not prove those cases.

## 7. STT, evaluation, and benchmark conclusions

Existing tests independently pass for known substitutions/deletions/insertions, rates exceeding 100% without clamping, separate human-reference WER and automatic disagreement, negations/amounts/dates/names/addresses/intent, role/time alignment, unmatched intervals, multiple speakers, mixed versus caller-only guards, absent/invalid timing, empty/long transcripts, hash mismatch, expiry, concurrent reference generation in one worker, cached reference reuse, and private report hydration. Synthetic labels are synthetic; no real human-verified transcript was invented.

F03/F04 show that numeric-sign semantics remain incorrect despite those tests. F02/F05 show supported policy behavior is less reliable than the packaged supported-case count suggests. Hallucination evidence and report consistency are checked by existing deterministic fixtures and stored-real-report inspection; **fresh live LLM accuracy was not independently measured** in this pass.

The packaged policy dataset is hand-labeled synthetic data, SHA-256 `799681cfbd87f5918c47cfe11617c6d3f9b93bc6e339470246d608506824e5e0`:

- Exact cases: **25/28 (89.29%)**.
- Supported cases: **24/24**; challenge paraphrases: **1/4**.
- Finding labels: TP **10**, FP **0**, FN **3**; precision **1.0**, recall **0.7692**, F1 **0.8696** on this dataset only.
- Failed challenges: `challenge-assure`, `challenge-lead`, `challenge-returned`.
- Independent QA adds a demonstrated false positive absent from this fixture. The packaged precision is not production precision and does not describe the new adversarial set.
- The CI benchmark command runs the older harness consistency benchmark, **not this default-failing full policy benchmark**. Do not remove challenges or lower thresholds to call the detector correct.

Independent API-versus-SQLite aggregation check found **7 stored calls = 2 real + 5 synthetic**, matching both list totals and all-time summary. Synthetic IDs remain clearly separated. Missing fact evidence and real-call STT prerequisites remain unscored rather than supplied with invented accuracy.

## 8. Real Bolna acceptance evidence

Using the already authorized completed test call, the independent script freshly read the actual Bolna execution and retrieved its original recording through the hardened downloader. No calling agent was modified and no new call was placed.

| Acceptance item | Independent result |
| --- | --- |
| Fresh completed execution and transcript availability | Verified from Bolna; saved original transcript byte-equal to returned transcript. |
| Fresh recording retrieval | Verified; **2,191,516 bytes**, `audio/x-wav`, **68.4835 seconds**; hash matches cached original. |
| Independent transcription | Existing cached Deepgram reference verified: **39 timed segments** bound to that recording hash. **No fresh Deepgram transcription was run in this pass.** |
| Speaker mapping | Reference roles remain **unknown**; diarization IDs are not assigned caller/agent identity. |
| Bolna utterance timing | Missing trustworthy utterance timings; not manufactured. |
| STT comparison | Metric correctly **null / Not scored**. No scored real-call accuracy claim. |
| Report and evidence reload | Actual backend and production browser reload verified. |
| Replay | Two authenticated local replays reuse the already persisted receipt/run; provider credential returns acknowledgment only. **Not a fresh Bolna-originated webhook delivery.** |
| No duplicate transcription | Cached reference POST succeeds unchanged even with Deepgram absent on the isolated server; browser playback/reload makes no reference submission. |
| Playback/navigation | Actual audio plays; supplied independent-reference timestamp after 10 seconds seeks and plays. Original Bolna timing navigation and aligned real finding navigation remain unavailable. |
| Retention/failure | Actual expiry tested with isolated synthetic artifacts/container. The real-call browser expiry state was a controlled 404, not deletion/expiry of the real recording. |

Private evidence: `real-acceptance.json`, `real-acceptance.log`, `browser-stt-demo.log`. No execution payload, personal transcript, recording URL, phone number, or credential is reproduced in this Git-visible report.

## 9. Browser evidence and limitations

Desktop **1440×1000** and mobile **390×844** were exercised. Existing access/STT suites and the extended run observed zero JavaScript `pageerror` events. That does **not** mean a clean console: the extended run captured **19 console error messages** and **69 aborted network requests**. All recorded requestfailed entries were `net::ERR_ABORTED`, including navigation/prefetch cancellation; they are not all separate product defects. Focused capture independently identifies the two font 403s and the legitimate policy POST 403 as real failures. Controlled 404/503 test responses are distinguished from actual backend responses.

Screenshots remain private in `.gstack/independent-qa/screenshots/`:

- `overview.png`, `calls-empty.png`, `synthetic-conversation.png`: real isolated frontend/backend flows.
- `failure-7.png`: blocked real policy save at the IPv4 demo origin.
- `defect-escalation-false-positive.png`: actual persisted confirmed false positive.
- `defect-negative-amount-zero-disagreement.png`: actual persisted incorrect zero-disagreement result.
- `real-cached-stt-unscored.png`, `mobile-stt.png`: authorized cached evidence, private images; no scored accuracy implied.
- `controlled-api-failure.png`: deliberately injected 503; error-state UI only.
- `policy-localhost-workaround.png`, `localhost-provider-unavailable.png`: successful actual CRUD/reload and missing-provider flow at localhost.
- `missing-provider-upload-error.png`: despite the original harness label, this IPv4 screenshot is an **origin/access-denial state**, not proof of provider failure. The later localhost test verifies the actual provider-unavailable path.

The mocked Calls UI suite verifies focus cycling, Escape restoration, evidence-to-transcript navigation, retry and stream-error presentation. It is not a real upload/provider integration test. The real STT suite verifies cached audio playback and reference seeking, not aligned finding navigation. Successful provider-backed upload-to-new-report processing was not rerun live.

## 10. Persistence, containers, and deployment paths

Verified against the independently built image:

- Non-root `voicescope` runtime; writable home and `/app/data`.
- Fresh health/startup; real SQLite initialization on a new named volume.
- Three synthetic reports survive container **replacement** and **restart**.
- Receipt survives restart; incomplete/expired claims have deterministic unit coverage.
- Primary SQLite mode **0600** under the runtime umask; recording/private responses are not cached.
- Synthetic recording serves 200 before expiry and 404 after expiry; review audio metadata becomes unavailable while the primary report remains.
- Missing provider returns a terminal SSE error and does not add a phantom run.
- Docker ignore canaries exclude `.env`, ignored private evidence, recordings, databases and sidecars while packaging required fixtures.
- Read-only online SQLite backup copied primary/STT/receipt evidence to an isolated directory; report, artifact hash, and receipt reads work from that copy.

Repository Docker and Railway declarations use `/app/data`; Compose mounts the same path. Monitoring, knowledge, cost, policy, STT and receipt databases use DATA_DIR/defaults or explicit overrides. The KB's derived Chroma policy cache defaults separately to `/tmp/chroma_db`, whereas transcript Chroma storage defaults under DATA_DIR unless overridden. Its source knowledge is SQLite/static text and can be rebuilt; F08 concerns stale index reconciliation. Hosted path overrides and actual volume bindings were not available to verify. Primary transcript/report retention is separate from 24-hour sliding STT-artifact retention; cleanup is on store initialization/access, not a background scheduler.

Not verified: real PostgreSQL outage/recovery/restore, Compose PostgreSQL integration, an unwritable hosted mount, all crash points, distributed multi-instance writes, OS image vulnerabilities, production media expiry, or a production backup/restore rehearsal. Application health is not proof of provider or database readiness.

## 11. GitHub and hosted release prerequisites

Fresh GitHub query: run **41174064636** on feature HEAD `299666b7...` has successful typecheck/test/frontend/benchmark/lint, **failed audit**, and **skipped Docker**. No green CI exists for the current uncommitted fixes. Local policy-audit success does not change that run or establish CI coverage of the dirty candidate. No CI job was restarted and no new commit was pushed.

Read-only Vercel checks succeeded. The production alias still resolves to Ready deployment **`dpl_BX9ycxRaTwQBND67XkWiCovkrGeV`**, created September 8. A newer Ready Preview is not production acceptance. Project environment inventory exposes names only: `API_KEY`, `BACKEND_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_API_KEY`; **no `OPERATOR_AUTH_USER` or `OPERATOR_AUTH_PASSWORD`** and no hidden production environment count were returned. No values were requested/decrypted. Deploying the new fail-closed frontend without operator configuration would not provide a usable authenticated demo. The public-prefixed key name is a configuration concern; its name alone is not proof it was bundled into client JavaScript.

No Railway CLI or backend deployment access is available for the required hosted checks. Exact missing evidence: backend service/image identity, actual secret-name configuration, persistent-volume/database bindings, authenticated health and run access, backup location/date, isolated restore evidence, and a tested backend/frontend rollback that retains the private access boundary. Vercel metadata access does not supply those backend facts.

No production deployment/settings/secret/database changes were attempted. Existing historical frontend artifacts do not establish a rollback that preserves the new operator gate. Approve and verify the access configuration, approved backup/restore procedure, data-path migration if needed, and authentication-preserving rollback before deployment. Main may trigger deployment; merge and deploy cannot be assumed independent without checking the host's actual Git integration.

## 12. Remaining verification boundaries and priority corrections

1. **Fix F01 first:** successful same-origin browser mutations and fonts at every supported private URL, with hostile-origin protection retained. Re-run the production browser test, not just plain-Request unit tests.
2. **Fix confirmed evaluation errors:** F02/F03 first, then F04/F05. Add the retained adversarial fixtures to supported regression suites without weakening existing assertions; keep uncertainty and source provenance intact.
3. **Close privacy gaps F06/F07** and test malformed saved source, startup errors, API output and persistent log sinks.
4. **Reconcile KB removal F08** with real embedded storage coverage.
5. **Assess/update the complete image tooling inventory F09**, retain the narrow Chroma assessment/expiry, and keep lower npm findings visible. No blanket waiver or package upgrade was performed here.
6. Decide how much post-persistence retry duplication is acceptable for the private demo. Document at-least-once behavior; if strengthened later, add transactional/source-call idempotency and interruption tests rather than an exactly-once claim.
7. Re-run relevant/full checks after fixes and obtain explicit authorization before committing or pushing. CI must run on the **exact reviewed feature commit**, including Docker; do not reuse the old green jobs.
8. Rehearse a private localhost demo only with the limitations visible. Fresh successful Deepgram submission, fresh Bolna-originated delivery/retries, real scored alignment, successful new provider-backed upload/report generation, and hosted backup/rollback remain separate unverified acceptance items.

Regression risk is **material**: the passing existing suites miss a framework-specific origin failure, money-transfer semantics, signed amounts, and some privacy/index lifecycle paths. Passing tests and a functioning cached recording do not establish production readiness. The current candidate remains **NO-GO** pending corrections and exact-artifact verification.
