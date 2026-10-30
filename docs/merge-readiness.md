# Merge verification, October 31, 2026

Decision: push the tested hardening changes to the feature branch. Hold the merge
into `main`. The Python dependency audit fails and hosted end-to-end acceptance
has not been established. A passing local demo does not establish production safety.

Starting feature commit: `80fef7a40f65ae5ad33aac813c9628ed682fc5b4`.
Remote `main` at inspection: `f9d459c75e7152e370afed838bc547dde9d0a2d5`.
No production secrets, provider configuration, infrastructure or deployment were changed.

## Confirmed defects and fixes

| Reproduction | Fix and coverage |
| --- | --- |
| Synthetic private files in a Docker context reached the image, including `.gstack`, nested SQLite files and recordings. | `.dockerignore` excludes these paths. Build-context canaries verify exclusion while preserving runtime JSON and policy fixtures. CI repeats this check. |
| A fresh writable data volume caused run persistence to return HTTP 500 because SQLite parent directories did not exist. Six new storage tests failed before the fix. | Monitoring, cost and knowledge stores create the configured parent directory. Six regression tests cover default and overridden paths. A container smoke test saves and restores reports using a named volume. |
| The non-root image user lacked a home directory, so Chroma's embedding cache failed with a permission error. The first image test run had 611 passes and one failure. | Docker creates the user's home and the application data directory before switching users. CI checks home permissions. |
| Whole-repository Ruff and mypy failed. | Environment bootstrapping now happens through an imported module before authentication settings are cached. A subprocess regression verifies ordering. Explicit interval types and nullable-value handling fix type errors without suppressing them. |
| Reference preparation could submit cached audio without its binding hash. | Fail before provider submission and leave the review unscored. A regression verifies no upload occurs. |
| The committed frontend lockfile did not match the updated installed Next.js version because local npm configuration disabled lockfile writes. | Project `.npmrc` enables lockfiles. Next.js and its ESLint configuration are 16.4.3; compatible transitive patches are locked. Verification uses a fresh `npm ci`. |
| The reliability benchmark CLI existed locally but was ignored and absent from Git. | Track the existing script so clean checkouts can run the same benchmark tests. |

The five call-detail tabs and default Findings view are preserved. No scoring
formula, speaker identity or timestamp was invented to make the real call score.

## Local verification

| Check | Actual result |
| --- | --- |
| Backend suite, working tree and clean staged-source snapshot | 612 passed |
| Backend suite inside the non-root Python 3.11 production image | 612 passed, including cold embedding-cache initialization |
| Frontend suite after fresh `npm ci` | 49 passed |
| Ruff, whole repository | Passed |
| mypy, configured scope | Passed, 125 source files; untyped function bodies remain outside the configured check |
| Frontend TypeScript and ESLint | Passed |
| Next.js production build | Passed on 16.4.3 |
| Existing harness benchmark, `--min-truth 0.7` | Passed on 10 fixtures; hallucination accuracy remains unmeasured |
| Docker build and private-file exclusion | Passed locally; image runs as non-root |
| Container report persistence | Three synthetic runs survived restart and replacement with the same named volume |
| Synthetic browser flow | Five tabs, evidence navigation, upload/error states, keyboard focus and mobile layout passed, zero page errors |
| Real-call browser flow | Original audio, reference timestamp seeking, report reload and controlled expired-audio handling passed, zero page errors |
| Production-mode frontend with public STT proxy disabled | Review, recording and reference routes returned 403 |
| Frontend dependency audit | Three low advisories; no moderate, high or critical advisories |
| Python dependency audit | Failed, three ChromaDB advisories; existing waiver unchanged, no new waivers |

Private evidence is under ignored `.gstack/merge-readiness/`. It contains sensitive
call material and must not be published. Browser runs reused the prepared reference
and submitted no additional recordings to providers.

## Real-call acceptance evidence and limits

An existing authorized completed Bolna execution was retrieved and replayed through
the authenticated local webhook. Its original transcript and source execution ID
were preserved, the evaluation report persisted, the original recording was fetched,
and the existing Deepgram integration produced 39 timestamped reference segments.
The private report reloaded with the saved reference. Cached preparation reused it.
An invalid API key returned 401; another configured key could not retrieve its
private cached audio and received 404.

This is a local webhook replay of an existing execution. No fresh Bolna-originated
delivery, new phone call, or hosted provider-to-report flow was verified. The report
processing status is partial because review is required; recorded pipeline stages
completed without pipeline errors. The real call has no trusted Bolna turn timestamps
and no confirmed caller mapping. Its STT metric remains null and it has no confirmed
STT errors. Aligned real-call finding navigation remains untested. Synthetic fixtures
exercise that navigation separately.

## Security and deployment blockers

The audit flags ChromaDB 1.5.9 advisories
[PYSEC-2026-3813](https://osv.dev/vulnerability/PYSEC-2026-3813),
[PYSEC-2026-3814](https://osv.dev/vulnerability/PYSEC-2026-3814) and
[PYSEC-2026-3815](https://osv.dev/vulnerability/PYSEC-2026-3815).
At verification time the audit lists no fixed release. VoiceScope uses an embedded
client; this check does not demonstrate an exploitable path in VoiceScope. It also
does not justify waiving these findings. Resolve the advisories or document a
supported applicability assessment before approving the merge.

Vercel inspection returned 403 for the connected account's team scope. Preview
requests redirected to Vercel authentication. The production frontend returned
200, but its API health request timed out after 20 seconds. Hosted backend health,
deployment configuration and rollback remain unverified. The timeout alone does
not establish an outage. No Railway credential or verified production database
backup and restore procedure was available.

Calls, policies and ordinary reports still use shared API-key access and global
storage. Private STT artifact separation is not company-level authorization. Public
STT proxy routes remain disabled by default. Do not expose the private review proxy
on a public shared-key frontend or claim multi-company isolation.

Use the loopback-only private demo for now. Before merging, resolve the audit,
obtain hosted inspection access, verify the deployment and rollback configuration,
and exercise a fresh completed-call delivery. Pushing this feature branch may create
another automatic Vercel Preview; it does not merge `main` or authorize production.

## Repeating the checks

```sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy . --ignore-missing-imports --exclude sdk/
.venv/bin/python scripts/run_benchmark.py --min-truth 0.7
cd frontend
npm ci
npm test
npx tsc --noEmit
npm run lint
npm run build
npm audit
```

The private real-call browser test needs the local review server, an authorized
saved run and its already-prepared reference. See `frontend/tests/stt-demo.browser.mjs`
for its environment inputs. Do not copy signed URLs, keys or recordings into reports.
The full 90-second demo script and STT interpretation limits are in
`STT_DEMO_READINESS.md`.
