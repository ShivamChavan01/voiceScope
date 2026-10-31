# Independent release verification — October 31, 2026

## Four separate decisions

| Gate | Decision | Scope and evidence |
| --- | --- | --- |
| **A. Safe to commit locally?** | **GO** | Current code passes the fresh functional, type, lint, build, browser and container checks. Private identifiers found in documentation were redacted. Preserve this reviewed candidate on the feature branch. This is not production approval. |
| **B. Safe to push the feature branch?** | **GO, after explicit user approval** | Push only the reviewed feature commit for CI/review. No push was executed. A feature push can run CI and create a hosting Preview; it must not merge main or change production. |
| **C. Safe to merge main?** | **NO-GO** | Main is production-linked. The new candidate has no exact-commit GitHub CI result, and production access/data-path/rollback prerequisites remain unverified. Known benchmark misses must remain an explicit product limitation. |
| **D. Safe to deploy production?** | **NO-GO** | Hosted authentication, reverse-proxy/TLS behavior, backend volume/database bindings, backup/restore and rollback are not verified. One measured local restart exceeded the repository's 30-second Railway health-check setting; verify the actual deployment's startup budget before deployment. |

The three documented paraphrase misses and raw dependency advisories are **not** called passing checks. Local commit/feature-push GO means the bounded candidate is safe to save and submit for review, with these limitations visible. It does not assert general detection accuracy, a vulnerability-free dependency graph, or production readiness.

## Exact tested artifact and starting state

- Repository: `ShivamChavan01/voiceScope`.
- Branch: `feat/voicescope-reliability-stt-demo` throughout verification.
- Starting local and freshly queried remote feature HEAD: `299666b7df94bacbd046f9e06b3e68c9b15d128b`.
- Starting local and freshly queried remote main: `f9d459c75e7152e370afed838bc547dde9d0a2d5`.
- Tests include the existing dirty release patch, not merely starting HEAD. Starting Git-visible inventory: **241 files**, with **143 changed/new paths against main** before this report. The full patch, initial status, per-file hashes, and changed-path review inventory were captured privately.
- Tested runtime/test/configuration fingerprint: **`bb9bcada5a3eb535eabef6fcdc5a90ca7cac46c2dca56374f78be8339620388a`**. It hashes sorted Git-visible non-Markdown relative paths, NUL, bytes, NUL. Documentation redactions/report additions do not change it.
- Fresh isolated source snapshot: `.gstack/final-verification/source`. It has no application dotenv file. The virtualenv executable path was preserved rather than resolving its symlink to system Python.
- Fresh production frontend build ID: **`IBftGy9Sb4wG-lt8bsJmk`**.
- Fresh Docker image: `voicescope-final-verification:local`, ID **`sha256:337fa48a450e29f909b9bc91ca92adbb45a1b68033861146b942ec77d692ec6b`**.
- The local commit is created only after the final staged-file scan, on the feature branch. Its full SHA is in the handoff and can be resolved with `git log -1 -- FINAL_RELEASE_VERIFICATION.md`. This avoids embedding a commit's own unknowable hash inside itself; the tested code is independently identified by the fingerprint above.

Repository/ancestor `AGENTS.md` searches found no filesystem instruction files; the user's supplied instructions applied. Review traced authentication/proxy paths, webhook receipt lifecycle, recording retrieval, STT source/alignment/cache handling, evaluation contracts, storage, logging, UI states, deployment files and tests. The complete changed-file inventory was inspected for unassessed skips, audit waivers and unsafe additions. Existing functional source was not modified during this verification pass.

## Environment and exact fresh checks

Host Python **3.12.3**, container Python **3.11.18**, Node **24.17.0**, npm **11.13.0**, pytest **9.1.0**, mypy **2.1.0**, Ruff **0.15.17**, Next.js **16.4.3**. Browser checks use the existing private Playwright installation and `/usr/bin/google-chrome`. No new application dependency was installed or upgraded by this pass.

Evidence directory for all rows: ignored **`.gstack/final-verification/`**, with a private parent directory. Commands used real tools; logs/JSON and exit files retain actual results.

| Check and command | Exit | Fresh outcome |
| --- | --- | --- |
| Snapshot cwd: `PYTHON_DOTENV_DISABLED=1 DATABASE_URL= /mnt/nvme0n1p10/voicescope/.venv/bin/python -m pytest -q` | **0** | **715 passed**, 69.60 seconds. One Starlette/httpx deprecation warning. `backend.log`. |
| Snapshot frontend: `npm ci` | **0** | Fresh lockfile installation; lower-severity audit warnings retained. `npm-ci.log`. |
| Snapshot frontend: `npm test` | **0** | **56 passed**, no failed, skipped, cancelled or todo tests. `frontend.log`. |
| `.venv/bin/python -m ruff check .` | **0** | All configured checks pass. |
| `.venv/bin/python -m mypy . --ignore-missing-imports --exclude sdk/` | **0** | No issues in 135 source files. Untyped-function-body notes remain; this is not complete static proof. |
| Snapshot frontend: `npx tsc --noEmit` | **0** | Pass. |
| Snapshot frontend: `npm run lint` | **0** | ESLint passes. |
| Snapshot frontend: `npm run build` | **0** | Optimized production build succeeds. |
| `docker build -t voicescope-final-verification:local .` | **0** | Current candidate independently rebuilt. |
| Full backend tests, mypy and Ruff in that image | **0** | **715 passed**, 111.26 seconds; mypy 134 source files and Ruff pass. `container-tests.log`. |
| Original independent QA probes, including seven webhook failure/concurrency cases | **0** | **15 passed**. All original eight correctness/privacy/index reproductions now pass. Provider execution is mocked for webhook failure tests. `adversarial.log`. |
| `.venv/bin/python .gstack/final-verification/security-probe.py` | **0** | **59 HTTP checks pass** plus a client-key scan. `security.log`, `security-results.json`. |
| `node tests/private-access.browser.mjs` | **0** | Actual production-mode auth, protected fonts/assets, real same-origin policy create/delete, cross-origin rejection and encoded disabled-STT paths. |
| `node tests/calls-ui.browser.mjs` | **0** | UI/focus/retry/evidence navigation regression suite. **API responses are mocked.** |
| `node tests/stt-demo.browser.mjs` | **0** | Actual cached authorized recording playback, supplied reference timestamp seeking, reload and mobile checks; zero new reference submissions. Expiry UI uses a controlled 404. |
| `node .gstack/final-verification/extended.browser.mjs` | **0** | All **9 journeys pass** against real isolated frontend/API/SQLite; controlled 503 is explicitly injected only for its error-state check. |
| `.venv/bin/python .gstack/final-verification/container-run.py` | **0** | Fresh volume, replacement, restart, SQLite/report and receipt persistence, recording expiry, private access and missing-provider terminal error. |
| `.venv/bin/python .gstack/final-verification/container-boundary.py` | **0** | 11 private context canaries excluded, 3 required fixtures retained; non-root/writable home and enforced embedded Chroma. |
| `.venv/bin/python .gstack/final-verification/receipt-restart.py` | **0** | Three HTTP acknowledgments for a synthetic pre-completed receipt remain identical before/after a real container restart. This is a replay, not fresh provider processing. |
| `python -m pip_audit -r requirements.txt --format json --progress-spinner off --timeout 20` using the existing isolated audit environment | **1** | Five Chroma records/four unique IDs. **Not a clean raw audit.** |
| `python -m tools.dependency_audit` using that audit environment | **0** | Pass **with the assessed, temporary Chroma exceptions**, not vulnerability fixes. |
| Complete installed-image inventory: `python -m pip_audit -r .gstack/final-verification/image-inventory.txt --no-deps --disable-pip --format json --progress-spinner off --timeout 20` | **1** | Same five Chroma records; no pip/setuptools findings. The installed inventory has 109 packages. |
| `python -m tools.dependency_audit --inventory .gstack/final-verification/image-inventory.txt` | **0** | Same narrow Chroma assessment; no newly waived dependency. |
| Snapshot frontend: `npm audit --json` | **1** | **21 findings: 19 moderate, 2 low, 0 high/critical**. |
| Snapshot frontend: `npm audit --audit-level=high` | **0** | Configured threshold passes; lower findings remain. |
| `PYTHON_DOTENV_DISABLED=1 .venv/bin/python scripts/run_benchmark.py --min-truth 0.7` | **0** | Legacy heuristic consistency benchmark, 10 cases, score 0.8500. Hallucination accuracy is **not measured**. |
| `PYTHON_DOTENV_DISABLED=1 .venv/bin/python scripts/run_reliability_benchmark.py --json .gstack/final-verification/policy-benchmark.json` | **1** | **25/28** exact cases. Known strict-threshold failure is preserved and quantified below. |
| Additional production build with three synthetic build-time credential canaries | **0** | Public-key-named, server-key and operator-password canaries are absent from every client static asset. `canary-build.log`, `build-secret-canaries.json`. No real secrets were used in that build. |
| `git diff --check`, current/staged file scans | **0 / no sensitive payload matches** | Final candidate excludes real keys, recordings, transcript excerpts, logs and data stores; metadata identifiers were redacted as described below. |

Container suite command:

```sh
docker run --rm --name voicescope-final-verification-tests \
  --env PYTHON_DOTENV_DISABLED=1 --env DATABASE_URL= \
  --env PYTHONPATH=/tmp/devtools:/app \
  --mount type=bind,source="$PWD/.gstack/final-verification/source/tests",target=/app/tests,readonly \
  --entrypoint sh voicescope-final-verification:local -c '
    python -m pip install --quiet --target /tmp/devtools \
      pytest==9.1.0 pytest-asyncio pytest-cov mypy==2.1.0 ruff==0.15.17 &&
    python -m pytest -q &&
    python -m mypy . --ignore-missing-imports --exclude sdk/ &&
    python -m ruff check .'
```

Browser suites run from the snapshot's frontend with `PLAYWRIGHT_MODULE`, `CHROME_PATH`, loopback URLs, cached run selection and private operator credentials supplied by an ignored launcher. No keys/passwords are printed. The new backend independently reported **Deepgram unconfigured** before testing; no paid provider call was authorized or triggered.

## Claim-by-claim result for RELEASE_FIXES.md

| Claim | Result and limit |
| --- | --- |
| Localhost upload/policy/font origin fix | **Tested.** Actual browser mutations/fonts succeed at IPv4 loopback. Unit tests use real NextRequest for IPv4, IPv6 and localhost and reject cross-alias/port/attacker origins. Upload reaches the actual backend and displays a terminal missing-provider failure; a new successful paid-provider upload is **not** claimed. |
| Money-transfer escalation fix | **Tested.** Financial-object/pronoun and mixed-refusal regression cases pass; persisted synthetic browser result has no false escalation finding. |
| `100` versus `-100` STT evidence | **Tested.** Synthetic aligned fixture gives one substitution/5 reference words = **20.0% estimated disagreement**, with an amount finding marked **Needs human review**. Synthetic human-reference tests separately exercise WER. No real ground truth is manufactured. |
| Signed numeric fact support | **Tested.** Opposite signs are unsupported; equivalent currency/Unicode-minus formats match; date/identifier separators remain distinct. |
| Negation/quoted/report policy handling | **Tested.** An affirmative guarantee followed by “not tomorrow” is detected; actual negation, reported/example suffixes and hypotheticals stay unconfirmed. |
| Private error/log fixes | **Tested with synthetic canaries.** Saved-source 422 errors and provider/startup handlers omit private payloads. Browser error rendering is actionable and no client credential canary is present. This is not a guarantee that every conceivable operator-supplied value is absent from access logs; URL/correlation metadata must remain private. |
| Stale reference knowledge | **Tested against embedded Chroma.** Shrink, clear, re-enable and failed-upsert cases pass. Old index remains unavailable on failure rather than being silently served as current. |
| Stale STT comparison cache | **Tested.** Older scored reviews/findings are withheld until re-compared; reference/audio remain; reads do not submit a provider request or renew expiry. Historical primary reports remain snapshots. |
| Installer toolchain/audit fix | **Tested.** Final image pins pip **26.2.2**, setuptools **84.1.0**; no advisories returned for either. Exact CI inventory-export command was executed unchanged and produced **109 separate package lines**. Suspected newline quoting failure was **not reproduced**. |
| Real-call playback and unscored state | **Tested from authorized cached artifacts.** 20 original turns and 39 independent segments render, reference timestamps seek/play, and reload preserves **Not scored**. The reference declares Deepgram provenance and matches the cached audio hash. Fresh provider provenance/availability is **not re-established** in this pass. |

## Security and persistence boundaries

- **Operator access:** Standard Basic challenge on frontend pages, assets and APIs; missing/short configuration fails closed. Backend company API key remains server-side. TLS is required outside explicit loopback. Frame denial and private no-store responses were tested. Reverse-proxy behavior on the actual hosted domain remains unverified.
- **Authorization:** One company, trusted operators. Primary run lookup is global intentionally. STT artifacts are scoped by API-key hash; that is not individual-user/tenant authorization. Valid webhook credentials cannot read runs, reports, policy resources or recordings, including when an invalid operator key is supplied.
- **Webhook authentication:** Separate constant-time-compared `X-Webhook-Key`, restricted to the completed-call POST and Bolna-shaped payloads. It is a shared-header secret, **not a provider HMAC/signature**. Real provider-originated delivery/signature provenance was not tested.
- **Input/SSRF boundary:** Bounded webhook bodies, invalid IDs/nonfinite JSON rejected; recording downloads require HTTPS/public pinned DNS, bounded redirects, MIME/size checks, and no cross-host credential forwarding. Existing direct/fake-network SSRF regressions passed. No destructive or production SSRF tests were run.
- **Retry/durability:** Atomic receipt claims serialize duplicates; active duplicates get 409/Retry-After; completed replays reuse persisted reports; write/readback failures do not acknowledge success. Cancellation releases the claim. A failure after report persistence but before receipt completion can cause another evaluation/report on retry: the independent characterization test observes this explicitly. This is **not exactly-once provider execution** or a durable queue/backfill service.
- **Storage/expiry:** Final-image synthetic reports survive real container replacement and restart on a new named volume. Private recording changes from 200 to 404 after actual synthetic expiry while the primary report remains. Receipt persistence and authenticated reload work. STT retention is 24 hours after the last write, cleaned on access; primary report/receipt retention is separate. Independent replica filesystems cannot coordinate.
- **Restart measurement:** An additional HTTP replay-after-restart probe first failed with a connection reset after an insufficient readiness wait. The corrected probe explicitly waits for authenticated persisted-run access; it reached readiness in **41.8 seconds**, then returned the same acknowledgment. No OOM/container crash was observed. Do not call this zero-downtime behavior or assume the repository's Railway `healthcheckTimeout=30` is sufficient on the actual host.
- **Images:** Fresh image runs non-root with a writable home/data path. Private context canaries and an actual `/app` file scan find no dotenv files, private evidence, recordings, logs or databases. Actual embedded-client initialization adds zero listening TCP sockets and exposes no Chroma server routes.

Screenshots of major flows and synthetic failure states remain in `.gstack/final-verification/screenshots/`. Extended browser results contain zero JavaScript page errors, one expected console error for the injected 503, and 54 aborted navigation/prefetch requests. These aborted requests are recorded, not misreported as 54 distinct application failures. Desktop 1440×1000 and mobile 390×844 were exercised.

## Reliability benchmark: all three misses

The unchanged hand-labeled synthetic dataset contains **28 cases**. No expected labels or thresholds were altered.

| Case | Synthetic input | Expected / actual | Root-cause boundary |
| --- | --- | --- | --- |
| `challenge-assure` | “I assure you your refund will arrive today.” | Confirmed same-day-refund policy match / **no finding** | Matcher recognizes specific guarantee/promise phrasing, not this assurance wording. |
| `challenge-lead` | Customer asks to speak with the team lead; agent says they will not let the customer speak with the team lead. | Confirmed escalation violation / **no finding** | Request/refusal patterns do not cover this team-lead/let-you-speak formulation. |
| `challenge-returned` | “The money has been returned to your card.” | Unverified completion claim requiring an action result / **no finding** | Completion patterns use specific refund/processed/issued/sent forms. |

Exact agreement **25/28 = 89.29%**. Supported cases **24/24**; challenge cases **1/4**. Finding-label counts: **TP 10, FP 0, FN 3**; precision **1.0000**, recall **0.7692**, F1 **0.8696**, **on this fixture only**. Policy findings: TP 7/FN 2; unverified claims: TP 2/FN 1. No production accuracy or held-out generalization is inferred. Other unsupported paraphrases can also fail; “three” describes this packaged dataset, not the total possible misses.

## Dependency audit assessment

- Raw requirements and complete-image audits both report **five Chroma records/four unique IDs**: `PYSEC-2026-311` twice, `PYSEC-2026-3813`, `PYSEC-2026-3814`, `PYSEC-2026-3815`.
- Exact pin **chromadb 1.5.9**; fresh [PyPI metadata](https://pypi.org/pypi/chromadb/json) reports 1.5.9 as latest stable. Raw records list no fixed version.
- Exception applies **only before 2026-11-07 UTC**, only to that version/ID set, only when no fix is supplied. Unknown advisories, versions, fixes, malformed/skipped inventories and expiry are tested to fail. It is not open-ended and was not expanded.
- The [pre-auth configuration injection](https://osv.dev/vulnerability/PYSEC-2026-311), [collection-update injection](https://osv.dev/vulnerability/PYSEC-2026-3814), [tenant authorization](https://osv.dev/vulnerability/PYSEC-2026-3813), and [SimpleRBAC scoping](https://osv.dev/vulnerability/PYSEC-2026-3815) records remain serious package findings. The tested application forces the embedded Rust API with no server authorization providers, no exposed Chroma server endpoints, and no caller-supplied embedding/model configuration. This supports the narrow local applicability assessment; **it does not patch Chroma or prove hosted configuration**.
- npm still reports **19 moderate/2 low**, rooted in minimatch glob amplification and deepmerge prototype poisoning. The configured high threshold passes; no high/critical npm advisory was returned. Raw package/range details are retained in `npm-audit.json`. No new advisory or pip/setuptools finding was returned by this scan.
- No OS-package image vulnerability scanner was run. Application dependencies other than the documented pins are not a completely hash-locked supply chain; a future rebuild requires fresh testing/auditing.

## Commit/privacy review and changes in this pass

**Low-severity documentation privacy finding, corrected:** Three distinct real execution/run identifiers appeared across five occurrences in `STT_DEMO_READINESS.md`, `docs/bolna-verification.md`, and `docs/stt-live-verification.md`. They were replaced with clearly labeled uppercase placeholders in the candidate documentation; private verification evidence retains the actual values. Those identifiers were already present in the starting feature commit; removing them now does **not** erase existing Git history. No history rewrite or force-push was performed. Identifiers are not credentials, and no unauthorized data read was demonstrated.

The scan compared configured credential values, local test credentials, actual recording URLs/phone values and real transcript excerpts against every candidate file without printing values. No keys, private transcript payloads, recording files, logs, databases, private-key patterns or files over 5 MB were found. Synthetic hand-labeled transcripts and example placeholders remain intentionally versioned. Public/static bundles also pass the independent synthetic build-time secret-canary test. This is targeted release evidence, not a retrospective certification of all Git history or every possible secret encoding.

An initial `git add` using the entire reviewed inventory returned 1 because unchanged script paths matched an ignore rule; it partially staged the intended release files. Staging was then narrowed to the reviewed changed paths, without resetting user work or force-adding ignored files. This administrative retry is separate from application test results.

Verification-only changes: the three documentation redactions and this report. No additional runtime bug was reproduced that required an application fix. Existing dirty source/test/configuration changes were preserved and tested as the release candidate. Final staging is restricted to the reviewed files and this report; ignored `.gstack`, dotenv, media and data stores are excluded. The final staged scan and `git diff --cached --check` must pass before the authorized local commit.

## GitHub workflow and remaining release gates

Fresh GitHub reads show the latest remote run **41174064636**, on the old feature commit: frontend/lint/typecheck/test/legacy benchmark succeeded, **audit failed**, **Docker skipped**. These results do not approve the new local commit. No remote CI was started or rerun during this pass.

After an approved feature push, these jobs must run on the **exact pushed SHA**:

1. `frontend`: fresh npm install, high-threshold audit, 56 tests, TypeScript, ESLint, production build.
2. `lint`: configured Python Ruff.
3. `typecheck`: Python 3.11, current requirements, mypy.
4. `test`: complete backend pytest with coverage upload. Local tests were run without the GitHub/Codecov upload; that external reporting step is not verified here.
5. `audit`: raw dependency evaluation through the explicit Chroma policy.
6. `benchmark`: legacy harness command with `--min-truth 0.7`. **This job does not run the default-failing full policy benchmark**; its known failure is reported above rather than hidden.
7. `docker`, after all dependencies succeed: build, complete installed-image inventory audit, private context canaries and non-root/runtime-fixture checks.

The feature push trigger is present; main remains production-linked and is not a target of this authorization. Browser scripts are opt-in/local and are not currently GitHub jobs. Do not label a skipped Docker job passed, or reuse old green jobs for a different SHA.

**Unverified / not executed:** fresh paid transcription or LLM analysis, fresh Bolna-originated webhook delivery/retry scheduling, real-call scored WER without timing/identity evidence, external hosted authentication/TLS routing, actual backend host/image/volume/database configuration, production backup/restore or rollback rehearsal, real PostgreSQL recovery, distributed replicas, and OS-level vulnerability scanning. Prior hosting claims were not treated as current proof. No production endpoint/data mutation, credential change, deployment or merge was performed.

Proceed with the authorized local feature commit after the staged checks; **stop before push and request approval**. Merge/deployment require a separate decision after exact-commit CI and the hosted prerequisites are established.
