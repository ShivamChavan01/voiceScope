# Live post-call Deepgram verification

Execution and run identifiers are redacted in this document. Uppercase ID placeholders refer to values retained only in private verification evidence.

Current release evidence is in [RELEASE_READINESS.md](../RELEASE_READINESS.md).
The live-service checks and counts below record earlier snapshots.

## Fresh verification — October 29, 2026

The completed execution documented below was retrieved again, with a fresh
authorized submission to the same existing Deepgram adapter. No new call was
placed. Current evidence and the exact demo script are in
[STT_DEMO_READINESS.md](../STT_DEMO_READINESS.md).

- Bolna execution HTTP 200, completed; recording 2,191,516 bytes, 68.4835-second
  two-channel WAV, verified against the cached SHA-256.
- Exact original transcript preserved: 20 attributed turns, no Bolna turn times.
- Fresh Deepgram reference: 39 timed segments, IDs `dg_0` and `dg_1`; neither ID
  was assumed to identify the caller. The operator could not confirm the mapping.
- Comparison correctly remained blocked, with no metric or confirmed errors.
  Real-call aligned findings and their timestamp navigation remain unverified.
- Private state, cached reference reuse and opted-in report reload passed. Invalid
  keys received 401; another valid key could not read the first key's artifacts.
  Main run access is still global, so this is not proof of tenant isolation.
- Chromium played the actual recording, sought using a real reference timestamp,
  rendered both source panels and reloaded without another provider submission.
  A 390px viewport had no page overflow and there were no uncaught page errors.
- A separate owner-scoped retention fixture returned 404 after expiry and removed
  its reference/row without changing the main demo artifacts. A controlled browser
  audio-404 response also produced an explicit error message.

Current validation: 596 backend tests, 41 frontend tests, standalone TypeScript,
frontend lint, production build, changed Python Ruff checks and whitespace checks
passed. Public STT proxy access remains disabled by default. Only the loopback
demo enabled it; production configuration is unchanged.

Private current evidence is under ignored `.gstack/stt-demo-readiness/`, with mode
0700 directories and private raw files. The historical `/tmp/voicescope-stt-live/`
files referenced below are no longer available. The first new Chromium attempt
failed due to a full `/tmp`; repository-local temporary storage allowed the check.
A repeat browser check was also restarted after the local production build
replaced Next.js artifacts. The final browser check passed against the restarted
frontend. These environment failures were not counted as successful checks.

## Historical verification — October 26, 2026

Verified locally on October 26, 2026, after the workspace owner explicitly authorized testing recordings with the existing Deepgram provider. No phone call was placed, no live calling pipeline was changed, and no production deployment, secret, agent, webhook, or billing configuration was changed.

## Actual services and recording

Bolna's authenticated [Get Execution API](https://www.bolna.ai/docs/api-reference/executions/get_execution) returned HTTP 200 for the existing completed execution `AUTHORIZED_TEST_EXECUTION_ID`. Its supplied transcript and original recording were used, without generating or rewriting source words.

| Evidence | Observed result |
| --- | --- |
| Execution status / reported call duration | `completed` / 72 seconds |
| Original recording | 2,191,516 bytes, WAV, 2 channels, 68.4835 seconds of recorded audio |
| Original Bolna transcript | 20 attributed turns; **zero turn timestamps** |
| Actual Deepgram transcription | Succeeded using the existing Nova-2 English adapter |
| Independent reference | 39 segments, all with start/end times; 2 diarization speaker IDs |
| Reference recording binding | SHA-256 matches the original audio served through the private API |
| Reference provenance | Automatic, not human verified |
| Local reference endpoint | HTTP 200 without a per-recording approval flag |
| Repeated reference request | Reused saved reference |
| State and report reload | Reference preserved; STT report summary hydrated correctly |
| Browser recording duration / buffer | Finite duration of 68.4835 seconds; full file buffered after proxy content-length fix |
| Result | **Blocked / not scored**, because coverage, roles and Bolna timing alignment are not established |

Two channels alone do not prove caller isolation. Two diarization IDs do not establish which voice is the caller. The differing execution and recording durations are preserved as reported and measured; neither value is substituted for missing utterance timings.

## Automatic browser workflow

A real Chromium browser opened the call in the private local frontend, then opened **STT quality**. The browser used the actual frontend proxy and backend, not mocked HTTP responses. The test began with only this verification run's private STT cache cleared to exercise first-open behavior.

- Opening the tab automatically retrieved the real recording and submitted it to Deepgram. No provider-approval checkbox or intermediate approval click was present.
- Exactly one reference POST was issued by that browser workflow. It returned the real timed Deepgram reference.
- The original recording played from the 10-second mark. The final audio check also established a finite 68.4835-second browser duration and the full buffered range. The proxy now reports the actual buffered audio byte length instead of discarding that metadata.
- Reopening the call reused the saved reference and issued no further reference POST.
- The 390px viewport had no page overflow, and the browser reported no page errors.
- The UI showed **Not scored**. It did not present model agreement as accuracy or manufacture WER.

There were two real transcription passes during verification: one through the API integration check and one to verify the complete automatic browser path. Repeated API requests and browser reopening reused the corresponding saved reference. This is a test of completed recordings, not live call monitoring.

## Automation and remaining limits

The configured Deepgram provider is authorized at workspace level. Missing references are prepared automatically when an eligible real call's STT review opens. The UI names the provider but does not ask for repeated approval. Synthetic demos, missing credentials, missing original transcripts, cached references, and recorded provider failures do not trigger automatic uploads. A failed review has an explicit retry action. Existing human references are preserved.

Concurrent preparation requests in the same backend event loop share one in-flight submission, including an outage result. Deterministic tests verify both success and failure. Cross-worker deduplication and durable background jobs remain unsupported. Opening a tab is the preparation trigger; this change does not add automatic submissions to call-completed webhooks.

This verification proves real recording retrieval, real provider transcription, timestamps, private persistence, reload, and automatic UI wiring. It does not establish transcription accuracy, human-verified ground truth, correct caller mapping, aligned WER, fresh Bolna-originated webhook delivery, or production availability. Reviewers still need to establish speaker coverage/roles and annotate Bolna timings before an aligned comparison is valid.

New STT routes remain blocked by default on the public shared-key frontend proxy. The verification frontend was enabled only on loopback, with a private temporary API key and isolated data paths. Production configuration is unchanged.

## Private evidence and regression checks

Raw execution payload, transcripts, audio artifacts, temporary configuration, API verification script, browser script, and JSON summaries are under `/tmp/voicescope-stt-live/` with private filesystem permissions. These may contain personal information and are intentionally excluded from this report and source control. Temporary evidence is not a durable production artifact.

Regression tests cover automatic preparation, explicit opt-out compatibility, fixed provider selection, no uploads from read-only GET, cached references, human-reference preservation, missing credentials, outage handling, same-worker concurrent submission sharing, and report persistence. See [STT contracts and setup](stt-quality.md) for the offline test commands.

## Recording upload follow-up

The original isolated STT preview had only recording/transcription credentials. Uploading through the full analysis pipeline attempted to initialize an unconfigured OpenAI provider and failed before the SSE error handler. HTTP 200 had already been sent. The frontend also accepted a stream ending without a terminal event, hiding the failure.

The local preview now uses the existing configured Groq analysis provider, with isolated database, cost, knowledge, and Chroma paths. No production configuration or secret file was changed. Pipeline startup is inside the stream error handler. The frontend validates progress events and requires a terminal result or error, reports empty/truncated/malformed streams, and automatically opens the persisted result after upload. The proxy no longer closes an already errored stream controller.

A real Chromium drag-and-drop of the original recording through `/api/v1/analyze/stream` verified Deepgram transcription, Groq analysis/report, persistence, automatic detail opening, and transcript rendering. The saved run `AUTHORIZED_TEST_RUN_ID` contains 852 transcript characters and 12 attributed turns. Its status is `partial` / review required; successful processing is not a clean-call verdict. An injected HTTP-200 empty stream then produced an explicit UI error without creating a result or making another provider submission. Browser page errors: zero.

Validation after this fix: 588 backend tests, 38 frontend tests, frontend lint, production build, changed Python Ruff checks, and diff whitespace checks passed. Private browser evidence is `/tmp/voicescope-stt-live/upload-summary.json`; it contains metadata rather than transcript content.
