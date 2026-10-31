# VoiceScope STT demo readiness — October 29, 2026

Execution and run identifiers are redacted in this document. Uppercase ID placeholders refer to values retained only in private verification evidence.

The latest safe-release review is [RELEASE_READINESS.md](RELEASE_READINESS.md).
It records the current uncommitted changes, fresh test counts, authenticated
single-company boundary, real-call replay and the separate merge/deploy decision.
Earlier counts and access recommendations below describe prior snapshots.

**October 31 verification:** 612 backend and 49 frontend tests pass. Configured
Ruff and mypy, TypeScript, ESLint and the Next.js 16.4.3 production build
pass. A real completed execution replay, original audio, Deepgram reference,
private report reload and browser seeking were checked locally. The real call
remains unscored for missing Bolna timestamps and unconfirmed speaker roles.
The Python dependency audit and unavailable hosted acceptance prevent a merge
recommendation. See [docs/merge-readiness.md](docs/merge-readiness.md) for current
fixes, evidence and deployment blockers. Earlier counts below describe prior runs.

**UI follow-up — October 30:** Styling, recording access and spacing were improved.
The original five tabs and default Findings view are retained: Findings, Transcript,
Speech diagnostics, STT quality and Evaluation checks. Technical evaluation output
is directly visible in its dedicated tab; assessment limitations remain expanded.
Listening in Transcript only reads or retrieves the Bolna recording and does not
prepare another Deepgram transcription. Frontend coverage is 49 tests. The scored
comparison blockers and private-access recommendation below still apply. Findings now displays the saved AI-generated call
summary and evaluator warnings before the separate policy findings, without
promoting a model summary or heuristic warning into a confirmed violation.

A fresh local browser check showed the uploaded real call's exact saved summary
and three evaluator warnings. The three existing synthetic scenarios were loaded
through the normal sample-call action and verified: zero policy matches, one
forbidden refund promise, and one escalation refusal. Both positive cases linked
to the original evidence turns. Real call data and the global policy configuration
were unchanged; no provider submissions occurred. Private verification metadata:
`.gstack/stt-demo-readiness/demo-ui-summary.json`.

**Recommendation: private local review demo. A scored real-call STT accuracy demo is blocked. Do not enable the shared-key public frontend for STT review. No deployment was performed.**

Real Bolna retrieval, a fresh authorized Deepgram pass, private persistence, report reload, original-audio playback, and reference-timestamp navigation were exercised. This recording has no Bolna turn timestamps, and caller/agent identity remains unconfirmed. The operator answered that they could not identify the speakers. Its result is correctly **Not scored**, with no claimed confirmed STT errors. Two models agreeing would not prove accuracy.

## 1. Starting state and existing functionality

Starting commit: `f9d459c75e7152e370afed838bc547dde9d0a2d5`. The repository already had extensive tracked modifications and untracked STT/reliability implementation and tests. Those changes were preserved. This is a review of that working tree, not a claim that all differences from HEAD were introduced in this pass. No commit, PR, secret-file edit, infrastructure change, or live-call pipeline change was made.

The preceding local checks were 590 backend and 38 frontend tests. Independently rerun at the start of this pass: 76 focused STT backend tests and 38 frontend tests passed. Earlier 588/590 counts in documentation describe earlier passes, not current totals.

The implementation already contained:

- FastAPI evaluation APIs, the existing transcription registry and Deepgram adapter; the main call pipeline and report storage use PostgreSQL or SQLite fallback. The Next.js frontend proxies requests with a server-side API key.
- Transcript-first Bolna ingestion preserving attributed source text and execution/agent metadata. STT review separately retrieves a completed execution's recording through authenticated Bolna APIs. It does not alter the live calling pipeline.
- A hardened recording downloader: execution UUID validation, bounded HTTPS redirects, public-address checks and DNS pinning, credential stripping across hosts, audio content/size checks, and local WAV metadata inspection.
- Deepgram word timestamps and numerical diarization labels. The source adapter groups real word times into segments and retains unknown roles. A speaker number or stereo channel is not proof of caller identity.
- Speaker/time alignment; deterministic substitutions, deletions, insertions and reference-word counts. WER requires a hash-bound, explicitly human-verified reference. Automatic references yield **estimated transcript disagreement**, never ground-truth WER. Incomparable coverage or missing evidence withholds rates.
- Bounded meaning-change heuristics and timestamped evidence with confidence explanations. These are English-oriented heuristics, not comprehensive entity/intent understanding. Automatic findings always require review.
- Private owner-key/run-scoped SQLite artifacts, filesystem restrictions, 24-hour sliding expiry, and opportunistic cleanup. Existing run transcripts have separate retention rules.
- Private review/audio APIs, opt-in report hydration, a default-disabled public STT proxy, and a call-detail STT tab with two transcript message panels.

Relevant code: `core/stt_quality.py`, `core/stt_recording.py`, `core/stt_sources.py`, `core/stt_service.py`, `stt_providers/deepgram_provider.py`, `storage/stt_reviews.py`, `api/stt_routes.py`, and `frontend/src/components/stt-*.tsx`.

## 2. Reproduced bugs and root causes

| Failure observed before fix | Root cause | Correction and regression coverage |
| --- | --- | --- |
| An encoded private path reached backend fetch while the public STT gate was disabled; test received 502 instead of 403. | Gate checked a raw path before URL/backend normalization. | Decode/validate segments before path construction and gating; reject ambiguous separators, traversal and malformed encoding. Restrict allowed prefixes to actual path boundaries. `frontend/tests/stt-proxy.test.mjs`: encoded/normalized bypass regression. |
| Confirmed recording scope, reference speaker mapping and Bolna timing annotations disappeared after reload. | Comparison used local copies; private storage had no annotation column and did not save the confirmed state. | Persist explicit choices and hash-bound annotations; migrate existing private databases without discarding rows. Reload frontend controls from saved state. API regressions cover re-comparison without retyping and automatic-reference provenance. |
| A caller-only comparison discarded the agent's saved timing annotations. | Persisting the filtered comparison transcript would lose the full source annotations. | Save the full validated annotation request, preserving all original words and roles; filter only for comparison. Regression retains both original speakers. |
| Changed source words invalidated annotations but the old WER and confirmed findings still appeared. | Source validation fell back to untouched text while retaining the old review. | Return a blocked, unscored review without old findings on annotation/source/hash mismatch; use the same validation for report hydration. Regression checks both API surfaces. |
| The opted-in run response carrying private STT evidence had no `no-store` header. | Only dedicated STT routes set private-response cache policy. | Set `Cache-Control: no-store` for private report hydration; regression checks the header. |

Before this pass, the preceding reinspection had also fixed expired-row resurrection and hydration when the primary report was null. Those regression tests remain and pass. They were not newly discovered in this pass.

## 3. Minimal UI and automation changes

- Reuse Deepgram's actual timestamps and previously confirmed speaker choices. Never copy automatic reference timing onto Bolna words, infer roles from `dg_0`, or estimate times from turn order/duration/latency.
- Keep original text unchanged. Highlight differing words within finding evidence using a bounded display-only diff; it does not compute alignment or metrics.
- Explain the metric as `(S + D + I) / reference words`, with an explicit automatic-reference accuracy limitation. Missing evidence is visibly unavailable. Rates may exceed 100% when insertions justify that value.
- Keep scoring setup collapsed, with timing JSON and human-reference inputs in a nested **Debugging** section. Full source transcripts and audio remain directly visible.
- Successful references are reused. Opening a missing eligible reference can trigger the existing authorized Deepgram preparation; GET requests and live-call callbacks do not upload. There is no new provider or repeated permission prompt.

Documentation checked against the current [Bolna execution payload](https://www.bolna.ai/docs/post-call/execution-payload), [Bolna execution API](https://www.bolna.ai/docs/api-reference/executions/get_execution), [Deepgram diarization](https://developers.deepgram.com/docs/diarization), and [pre-recorded transcription API](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded). Bolna's documented plain transcript supplies no turn timestamps. The actual execution also supplied no usable turn timestamps. Undocumented internal fields are not treated as a reliable alignment contract.

## 4. Files changed in this pass

| Files | Purpose |
| --- | --- |
| `core/stt_service.py` | Persist/reuse confirmed setup, validate saved annotations and withhold stale reviews. |
| `storage/stt_reviews.py` | Add private annotation storage with an additive schema migration and existing expiry behavior. |
| `api/stt_routes.py`, `api/routes.py` | Consistent validated report hydration and private cache headers. |
| `frontend/src/app/api/[...path]/route.ts` | Canonical path validation before the private STT gate. |
| `frontend/src/lib/stt-quality.ts` | Saved setup restoration and bounded display diff. |
| `frontend/src/components/stt-review.tsx`, `stt-results.tsx`, `frontend/src/app/globals.css` | Restore confirmed controls, collapsed debugging, evidence highlights and metric explanation. |
| `tests/test_stt_review_api.py`, `tests/test_stt_artifacts.py` | Six additional backend cases, including migration, expiry, source changes and reload. |
| `frontend/tests/stt-quality.test.mjs`, `stt-proxy.test.mjs` | Three additional frontend cases and expanded evidence rendering checks. |
| `frontend/tests/stt-demo.browser.mjs` | Opt-in real-service browser smoke check, using an already cached reference. |
| `docs/stt-quality.md`, `docs/stt-live-verification.md`, this report | Current verification and limitations, separate from historical checks. |

Private test evidence/scripts live in ignored `.gstack/stt-demo-readiness/`; they are not application features or source fixtures. Raw recordings, transcripts, API keys and execution payloads are intentionally omitted from this report.

## 5. Verification commands and results

- `.venv/bin/pytest -q`: **596 passed**, one Starlette/httpx deprecation warning. Re-run after the final stale-review correction; see private `final-backend.log`.
- Focused API/artifact regression run after that correction: **41 passed**.
- `npm --prefix frontend test`: **41 passed**. Node reports an existing module-type detection warning.
- `cd frontend && ./node_modules/.bin/tsc --noEmit`: passed.
- `npm --prefix frontend run lint`: passed.
- `npm --prefix frontend run build`: passed; Next.js production build and TypeScript checks.
- `.venv/bin/ruff check core/stt_service.py api/stt_routes.py api/routes.py storage/stt_reviews.py tests/test_stt_review_api.py tests/test_stt_artifacts.py`: passed.
- `git diff --check`: passed.
- Opt-in Chromium smoke check: real playback, reference-timestamp seek, transcript rendering, reload/cache reuse, narrow viewport, and a controlled expired-audio error response. No page errors and no new provider submissions during browser checks. Real-call finding navigation remains unverified because this call has no aligned findings.

Browser command (use existing Playwright/Chrome locations appropriate to the machine; no package install required):

```bash
cd frontend
STT_DEMO_RUN=bolna-stt-74c12d45 \
PLAYWRIGHT_MODULE=/home/shivam/.gstack/repos/gstack/node_modules/playwright/index.mjs \
CHROME_PATH=/opt/google/chrome/chrome \
TMPDIR=/mnt/nvme0n1p10/voicescope/.gstack/stt-demo-readiness/browser-tmp \
node tests/stt-demo.browser.mjs
```

The first browser launch failed because the root filesystem holding `/tmp` was full. It was retried with a private repository-local temporary directory. No unrelated files were deleted. Provider failures, absent timestamps/audio, malformed inputs, synthetic human WER, insertions/deletions/substitutions and meaning-changing discrepancies have deterministic automated coverage; this is not proof of a real provider outage or independently verified accuracy.

## 6. Fresh real-call acceptance evidence

The historical October 26 report is not the evidence for these results. On October 29 an existing authorized completed execution `AUTHORIZED_TEST_EXECUTION_ID` was retrieved again. No new call was placed and no webhook delivery was tested.

| Acceptance step | Observed result |
| --- | --- |
| Authenticated real Bolna retrieval | HTTP 200, execution status completed. |
| Exact transcript preservation | Original run text matched the retrieved payload; 20 attributed turns, zero timed turns. |
| Recording | 2,191,516 bytes, WAV, 68.4835 seconds, two channels; retrieved bytes matched the stored SHA-256. Channel count did not establish speaker coverage. |
| Independent transcription | One fresh authorized submission to the existing Deepgram adapter; 39 timed segments, numerical IDs `dg_0` and `dg_1`, no human-verification claim. |
| Speaker coverage and alignment | Not confirmed; operator could not identify roles. No fabricated mapping or Bolna timestamps. |
| Comparison and findings | API returned blocked, metric null, no confirmed errors. This is an inspected unavailable result, not a successfully aligned comparison. |
| Persistence | Repeated reference preparation reused the same cached reference; state and private report reloaded consistently. General call evaluation was deliberately not rerun. |
| Browser | Both transcript panels rendered; actual recording decoded/played; reference timestamp button sought and played. Zero uncaught page errors. Reload did not submit audio again. |
| Authentication | Invalid API key returned 401. A second valid key could not read the first key's cached audio/reference. This proves artifact partitioning, not tenant/run authorization. |
| Retention | A separate owner-scoped expiry fixture copied the authorized artifacts and advanced its expiry. Audio returned 404, reference became unavailable, row was purged, main demo artifacts remained unchanged. UI also displayed a controlled 404 audio error. |

The local run `bolna-stt-74c12d45` is an STT-only import, clearly marked partial with an explanation that general call evaluation was not rerun. It contains no invented policy results or call-quality score. Evidence summaries: `live-summary.json`, `retention-summary.json`, `browser-summary.log` in the private ignored directory. Audio, execution and full source state are private files, not committed fixtures. The older `/tmp/voicescope-stt-live/` evidence is no longer available on this machine.

## 7. Security and retention limitations

- **Shared API keys are operator credentials, not user identities.** Main run lookup is global. Although one key cannot read another key's cached artifacts, another valid key can initiate its own review for a globally visible run using server-side Bolna credentials. There is no tenant/run ACL. Do not advertise cross-user isolation or expose this to untrusted operators.
- The public frontend has no visitor authentication. `STT_REVIEW_PROXY_ENABLED=true` is only a feature gate, not authentication. Keep it disabled publicly. In this check it was enabled solely on a loopback frontend using a temporary local key and isolated data.
- The private artifact directory is mode 0700 and SQLite file 0600. Audio responses, review responses and opted-in report hydration use `no-store`. This is filesystem access control, not encryption-at-rest or a backup deletion guarantee.
- Expiry is 24 hours since the latest save, not an absolute call-age limit. Reads do not extend it. Cleanup runs when a store is constructed; there is no scheduled sweeper or hard wall-clock erasure guarantee. Provider-side retention is governed separately by the configured Deepgram account.
- Original run transcripts use the platform's existing storage/retention and can remain after private artifacts expire. Expiring STT artifacts does not erase those transcripts or Bolna's original recording. Expired/deleted upstream recordings cannot be recovered by this module.
- Private SQLite and submission deduplication are local to one instance/worker. No distributed job queue, cross-worker deduplication, multi-instance artifact storage, or concurrent schema-migration guarantee is claimed. Reference creation is request-bound with a timeout.
- The proxy buffers complete audio and the API does not implement HTTP range streaming. Seeking was verified for this WAV only, not every format/browser. There is no proof of long-call scalability from this short recording.
- `railway.toml` mounts `/app/data` but does not itself set `DATA_DIR`/`STT_REVIEW_DIR`. A future approved deployment must explicitly use a writable private persistent path and verify runtime permissions. Existing Docker non-root execution and a volume declaration alone do not prove deployed durability. No production setting was changed.

## 8. Deployment recommendation and blockers

Use the running private demo at **http://127.0.0.1:3049/runs** (backend loopback port 8049). Local artifacts expire and the process is not a durable deployment. Keep the ephemeral keys off screen and out of source control.

Before presenting a **scored real-call comparison**, a reviewer must establish actual recording coverage and reference speaker mapping, then provide valid Bolna timing annotations preserving original words/roles. Human WER additionally needs a separately listened-to, verified reference; an automatic reference must retain estimated-disagreement labeling. These steps were not completed, so the complete scored acceptance criterion remains blocked.

Before any hosted STT demo: establish authenticated operator access and run authorization, approve deployment, configure private persistence and verify retention on the actual host. A public shared-key demo is not recommended. Production readiness is not established by the passing tests.

## 9. Exact 90-second demo recording steps

Preparation, outside the recording: confirm both local services are running, the real authorized reference is cached and unexpired, and no secrets/raw API payloads are visible. Open `/runs`. If artifacts expired, use the existing authorized retrieval/preparation flow and allow it to finish before filming. Do not reuse a stale screenshot as a live result.

1. **0–10 seconds:** Open the real STT-only run. Say: “VoiceScope reviews completed calls; this is a real completed Bolna recording. General call analysis was not rerun in this test.”
2. **10–30 seconds:** Open **STT quality**, play the original recording and pause. Show the original Bolna and separate Deepgram message panels. Say: “The original transcript is preserved. A separate transcription pass supplies independent evidence, not ground truth.”
3. **30–45 seconds:** Click a Deepgram timestamp after ten seconds. Show playback moving there. Say: “These are actual provider timestamps. Bolna did not supply turn times for this call.”
4. **45–60 seconds:** Show **Not scored** and its reasons. Say: “I cannot yet confirm which diarization speaker is the caller, so the system refuses an invalid caller-only comparison or invented accuracy score.”
5. **60–75 seconds:** Expand **Set up a scored comparison**, then the nested **Debugging** section. Briefly show coverage/role confirmation and timing annotation options. Say: “Confirmed setup is saved. Automatic comparisons remain estimated disagreement; only a verified human reference supports WER.” Do not fill in guessed identities/times or claim real findings here.
6. **75–90 seconds:** Reload, reopen the call and STT tab. Show that the reference and unavailable state persist without a new transcription. Say: “Playback, independent transcription and private reload work. Aligned real-call scoring awaits verified speaker coverage and timing evidence.”

For a separate developer appendix, run the deterministic synthetic regression tests to demonstrate negation/amount highlights, known WER edit counts and confirmed-versus-review states. Label them synthetic; do not present those fixtures as findings from this real call.
