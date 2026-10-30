# Review branch verification — October 30, 2026

October 31 follow-up: [merge-readiness.md](merge-readiness.md) supersedes the
verification table below. Backend tests now pass 612 cases, frontend tests pass
49, configured Ruff and mypy pass, and the frontend builds on
Next.js 16.4.3. CI now also runs on this feature branch and checks the frontend.
The Python dependency audit fails on three ChromaDB advisories. Main remains held;
the user authorized merging only if verification succeeds. The remaining text is
the historical October 30 snapshot.

Branch: `feat/voicescope-reliability-stt-demo`.
Starting commit: `f9d459c75e7152e370afed838bc547dde9d0a2d5`.

This branch captures the existing local reliability, policy evaluation, speaker
attribution, post-call STT, Calls UI, regression tests and documentation work.
The five call-detail tabs remain accessible, with Findings opening first.
Generated reports and evaluator warnings are visible separately from policy findings.

## Fresh checks before committing

| Check | Actual result |
| --- | --- |
| `.venv/bin/pytest -q` | 596 passed; one Starlette/httpx deprecation warning |
| `npm --prefix frontend test` | 49 passed |
| Frontend `tsc --noEmit` | Passed |
| Frontend ESLint | Passed |
| Frontend production build | Passed |
| Ruff on all 55 changed Python files | Passed |
| `git diff --cached --check` | Passed |
| Harness benchmark CLI, minimum 0.7 | Passed; hallucination accuracy remains explicitly unmeasured |
| Whole-repository Ruff | Failed: 10 E402 import-order errors in unchanged `main.py`; reproduced against the starting commit |
| Whole-repository mypy | Failed: 25 errors across eight files; baseline comparison was not performed for mypy |

The mypy errors involve optional timestamps/hashes, heterogeneous interval
group typing, benchmark variable reuse, return annotations, and enum arguments.
They remain unresolved. Passing runtime tests does not make the Python type check
or the complete CI pipeline green. The configured GitHub workflow runs on pushes
to main and pull requests targeting main; a feature-branch push alone does not
run that workflow. No pull request is part of this push.

Browser verification from this session exercised five-tab navigation, the real
saved call summary and its three warnings, synthetic policy evidence navigation,
recording playback/retry, error states, keyboard focus, uploads and mobile layout.
No additional provider submissions were made during those browser checks.
See `STT_DEMO_READINESS.md` for exact real-call evidence and limits.

## Artifact and credential review

Candidate source files were checked for matches to configured credentials,
credential-shaped values, private-key blocks and unexpected binary artifacts;
none were found. This is a targeted pre-push check, not a comprehensive security
audit. Recordings, signed recording URLs, local credentials, `.gstack` evidence,
SQLite databases and scratch directories are excluded. The ignore rules also
exclude local test SQLite files and root-level scratch directories.

## Remaining product limits

- Company login, memberships and cross-company authorization are not implemented.
- Fresh Bolna-originated webhook delivery and durable ingestion/retries remain
  unverified or incomplete; completed recording retrieval was verified separately.
- The real-call STT rate stays unavailable without confirmed speaker coverage and
  valid Bolna timing annotations. Automatic references are not ground truth.
- Public STT review is disabled by default. The private local demo does not prove
  secure hosted multi-company operation.
- Deployment, production configuration changes and merging into main require
  separate authorization. This review branch preserves the current main branch.
