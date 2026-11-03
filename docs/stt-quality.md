# Post-call STT quality review

## Signed-number comparison contract
Current comparisons identify their rules as `reference_alignment_v3`. Leading numeric signs, Unicode minus and currency/sign placement are preserved; for example, `100` and `-100` differ, while `-$100` and `$-100` normalize together. Combining marks stay with their words, including Hindi vowel signs. Hyphens inside dates/identifiers remain separators. Written numeric-sign changes are also flagged for review. These are bounded token/meaning checks, not complete semantic understanding.

Previously cached scored comparisons or findings without the current rule version are withheld until an operator compares again. Audio, reference and annotations are retained subject to their existing expiry; reading does not submit audio or extend retention. Verified WER still requires supplied timing and speaker attribution. The automatic whole-call estimate below exposes inferred alignment and never represents transcription accuracy.

Release follow-up: [RELEASE_READINESS.md](../RELEASE_READINESS.md) supersedes the
older counts and access assumptions below. The frontend now has standard HTTP
Basic operator authentication, plus independent backend API-key protection.
STT proxy access still defaults to disabled. This is a single-company boundary;
API-key artifact hashing is not per-user authorization. See
[private deployment](private-operator-deployment.md) for secure configuration.

This module compares a completed call's original Bolna transcript with a separate transcription pass or a human-verified reference. It never monitors live calls or changes agent speech, network behavior, or the calling pipeline. It identifies possible transcription problems; it cannot repair an ongoing call.

## Latest demo-readiness pass — October 29, 2026

See [STT_DEMO_READINESS.md](../STT_DEMO_READINESS.md) for the current audit,
596 backend / 41 frontend test results, fresh real-service verification, and demo
steps. The earlier checks below are historical passes, not the latest totals.

This pass fixed encoded-path bypasses of the disabled public STT proxy, private
report cache headers, and loss of confirmed comparison setup on reload. Private
SQLite storage now adds an `annotations` column without replacing existing rows.
Confirmed recording scope and explicit reference roles persist; Bolna annotations
retain the full original transcript and are bound to its recording hash. Invalid
saved annotations withhold the old score and findings in both review and report.
Expiry removes annotations with the other private artifacts.

Findings now highlight differing words and explain the metric formula. The diff
is display-only. Advanced timing JSON and human-reference inputs are nested under
Debugging. The main setup remains collapsed. No speaker identity, Bolna timing or
ground truth is inferred by these UI improvements.

The fresh real recording and separate Deepgram reference are available in a
private loopback demo. The recording's caller mapping is unconfirmed and its Bolna
transcript has no turn timestamps; it remains unscored. Public STT proxy access
must remain disabled: API-key artifact partitioning does not provide tenant/run
authorization, and the shared-key frontend does not authenticate visitors.

## Earlier reinspection on October 29, 2026

The existing worktree already contained the post-call module, private artifact store,
Deepgram word metadata adapter, API routes, report integration, and call-detail UI.
These were inspected and retained rather than rebuilt. The baseline was 588 backend
tests and 38 frontend tests passing. After the two fixes, the full backend suite
passed with 590 tests (one existing Starlette/httpx deprecation warning).
Frontend lint and the production build, including
TypeScript checking, also passed during this review.

Two additional regression cases failed before their fixes:

- Saving a new review after an artifact expired could renew the row's lifetime while
  retaining its expired recording and reference. `STTReviewStore.save` now deletes
  the expired owner/run row inside the same transaction before creating new data.
  A test advances the clock past retention and verifies that no old audio, metadata,
  or reference reappears.
- Hydrating STT evidence into a run with `report: null` raised an exception. Report
  hydration now initializes an absent primary report while preserving existing
  report fields. An API regression test verifies that human-reference evidence is
  still available when the primary report is missing.

Tests for this review use synthetic transcripts, controlled provider responses, and
temporary storage. No recording was resubmitted to Deepgram, and no fresh browser
or live-provider check was performed in this pass. The October 26 real-recording
verification below remains historical evidence, not a newly repeated test. No
production configuration, secrets, calling pipeline, or deployment was changed.

## Repository audit and implementation boundary

| Existing component | Finding | Reuse / change |
| --- | --- | --- |
| FastAPI `api/routes.py` | Transcript-first Bolna ingestion; audio download is the fallback. | Preserve the exact original attributed transcript in `evaluation.stt_source`. Add explicit review routes. |
| Bolna integration | Source execution and agent IDs persist. Recording URLs can expire. Stored transcripts are plain role-prefixed text, without utterance timings. | Retrieve the original recording on demand through Bolna's authenticated execution recording endpoint. Do not guess timestamps. |
| STT registry | Deepgram, Whisper and Gemini adapters exist. Deepgram is already supported; its word timings previously did not reach the evaluation. | Retain Deepgram word metadata. The new workflow selects only Deepgram, under workspace authorization; no repeated per-recording checkbox or fallback provider. |
| Speaker attribution | Transcript labels and inferred roles already have separate provenance. Diarization numbers do not establish caller identity. | Preserve Bolna's explicit roles; require listening and explicit mapping of reference speaker IDs. Do not invoke model role inference for scoring. |
| Evaluation pipeline | Transcription → speaker attribution → analysis / policy checks → report → harness; synchronous and SSE variants. | Run STT quality separately, when the operator opens an eligible completed-call STT review. Leave existing pipeline execution unchanged. |
| Persistence | Full evaluations in PostgreSQL or SQLite. Uploaded audio is not retained as a standard call artifact. | Store private, expiring STT artifacts separately in SQLite. Hydrate the requesting operator's report on reload. |
| Frontend | Next.js call-detail drawer and a shared-key proxy without visitor authentication. | Add **STT quality** to call detail. Block new STT proxy routes by default. |

Official schemas checked: [Bolna execution payload](https://www.bolna.ai/docs/post-call/execution-payload) and [Deepgram diarization word fields](https://developers.deepgram.com/docs/diarization). Bolna's documented plain transcript does not provide the utterance start/end fields this comparison needs. Call duration, latency, and turn index are not substitutes.

## Contracts

- `scope` is `caller_only`, `mixed`, or `unknown`. A reviewer establishes audio coverage by listening. A channel count, including stereo, proves neither caller isolation nor speaker identity.
- All scored segments need explicit caller/agent roles and valid recording-relative `start` / `end` seconds. Negative, nonfinite, reversed, or half-present timings are rejected. Known recording duration bounds the intervals.
- Mixed audio and caller-only transcripts are compared only after the mixed reference is explicitly attributed and filtered to caller speech. An unsegmented or unknown-role mixed reference is blocked. Mixed Bolna speech cannot be compared against a caller-only reference.
- Both transcripts must come from the same recording. The reference carries its SHA-256. This binds the submitted reference to a recording; it does not establish the reference's truthfulness.
- Human references require `source: "human"`, `human_verified: true`, a nonblank `verified_by`, and the recording hash. The reviewer attests that the reference is complete and correct for the chosen speaker scope after listening. This is an operator attestation, not an automated verification of human work.
- A Deepgram reference remains automatic even if another model agrees. A separate pass may share the original recognizer's model family. There is no independence or accuracy claim from model agreement.

Segments are grouped by overlapping intervals **within each role**, sorted by recording time. Nonoverlapping speech stays separate, and unmatched intervals count as insertions or deletions. Results use interval boundaries, not an invented exact timestamp for each disputed word. Broad timings can hide alignment errors; reviewers must annotate accurately. The first version has no forced alignment or automatic timing reconstruction.

Tokens use Unicode NFKC, case folding, punctuation removal, and preserved apostrophes / numeric and currency tokens. Written and spoken number formats are not treated as automatically equivalent. Tokenization is not a universal multilingual WER standard.

The Levenshtein calculation returns substitutions `S`, deletions `D`, insertions `I`, and reference words `N`. Deterministic ties prefer substitution, then deletion, then insertion.

| Reference | Metric | Finding status |
| --- | --- | --- |
| Human verified, timed and role aligned | **WER = (S + D + I) / N** | Confirmed STT error, based on that submitted reference |
| Automatically transcribed, timed and role aligned | **Estimated transcript disagreement = (S + D + I) / N** | Needs human review |
| Original timing absent, complete mixed conversation with distributed unique reference anchors | **Estimated whole-call transcript disagreement**, with explicit inferred alignment | Needs human review; original timings remain absent |
| Timings missing and automatic support insufficient | Unaligned text discrepancy only; **no aggregate rate** | Needs human review |
| Audio / hash / scope / speaker / reference unavailable | Blocked; **no rate** | Issue explains the missing prerequisite |
| Retrieval or provider outage | Failed; **no rate** | Sanitized failure; retry available |

A rate can exceed 100% when insertions exceed the reference length. It is never clamped. An empty or zero-word reference cannot supply a denominator. Oversized intervals produce a partial review with the aggregate rate withheld, rather than a rate for only the easy intervals. Limits: 25 MB recording, 120,000 transcript characters, 2,000 segments, 800 words per aligned interval.

Meaning-change flags use bounded English rules for negation, amounts, dates, contextual names and addresses, intent keywords, and numbers. These checks are incomplete and can overflag changes. Automatic findings never become confirmed errors. High/low confidence describes evidence quality, not a calibrated probability. Each finding includes both texts, role, interval if known, category, severity, status, explanation, confidence basis, and edit counts.

## Private local setup and review

Use the normal backend setup from the README. Set `BOLNA_API_KEY` securely on the backend to retrieve recordings. Set `DEEPGRAM_API_KEY` only if using automatic references. A human-reference workflow does not need Deepgram credentials.

Artifacts default to `DATA_DIR/stt_reviews/reviews.sqlite` (or `./stt_reviews/reviews.sqlite`). Override the directory with `STT_REVIEW_DIR`. The directory is mode 0700 and the database is 0600. Configure a private persistent volume; files are not encrypted by this module. Artifacts expire 24 hours after their last write and are purged on subsequent store access. Deleting a run also deletes its STT artifacts. Do not include this directory in backups or source control without a deliberate retention policy.

Artifacts are partitioned by a SHA-256 of the authenticated API key plus run ID. This is key scoping, not a complete multi-tenant authorization system. Existing run metadata still follows existing application permissions. Do not rotate a key expecting its old artifacts to remain accessible.

**Do not enable the new routes on the public shared-key frontend.** They are blocked unless `STT_REVIEW_PROXY_ENABLED=true` is set on a private, access-controlled frontend. For a loopback-only local demo, set this in the frontend process environment before starting it. No production configuration has been changed. The proxy forwards `X-STT-Review: 1` only when enabled; ordinary shared-proxy run detail does not hydrate private STT report evidence.

The workspace owner authorized the existing Deepgram provider for recordings on October 26, 2026. Opening an eligible real call's STT review now automatically retrieves its completed recording and generates a missing Deepgram reference. There is no repeated provider-approval checkbox. The UI still names Deepgram; this authorization does not extend to an unconfigured new provider.

1. Open **Calls → call detail → STT quality**. A real call with an original Bolna transcript and configured Deepgram prepares its missing reference automatically. Synthetic demos and calls without transcripts or credentials do not auto-submit.
2. Existing references, including human-verified ones, are reused. A recorded provider failure does not trigger repeated uploads every time the tab opens; use **Create Deepgram reference** to retry. No fallback provider is used.
3. Open **Set up a scored comparison**. Listen, establish mixed versus caller-only recording coverage, and map each reference `dg_N` ID to caller or agent. These confirmations establish evidence, not provider permission. Unknown coverage or roles prevent scoring.
4. Load original Bolna words for timing annotation if necessary. Preserve their words, order within each role, and roles; edit segment boundaries and times based on the recording. Without these timings the result stays unscored.
5. Select caller-only or both speakers, then compare. Review both texts and use **Listen at** for the original interval. Results survive reload until expiry.

For a human-reference workflow without an automatic upload, retrieve the recording through the recording-only API first, supply the verified reference through the comparison API, then open the UI. A stored human reference is preserved and prevents automatic transcription. The recording-only endpoint never invokes Deepgram.

The UI puts results and original audio first, followed by both full transcripts as message panels. Each source scrolls independently; rows do not imply time alignment. Supplied reference timestamps link to the original recording. Missing timing and unknown roles stay explicit. Speaker mapping and manual JSON inputs are collapsed under **Set up a scored comparison**; those inputs remain an operator debugging interface, not a polished annotation editor.

## API

All routes require the existing valid `X-API-Key`. Responses are `Cache-Control: no-store`. Replace `RUN_ID` with an existing completed Bolna-backed run; no credentials belong in URLs.

| Method | Path suffix after `/api/v1/runs/RUN_ID` | Purpose |
| --- | --- | --- |
| GET | `/stt-review` | Source, private reference, review, recording metadata, provider availability |
| POST | `/stt-review/recording` | Retrieve / reuse original Bolna recording; no STT upload |
| POST | `/stt-review/reference` | Body `{"provider":"deepgram"}` (or `{}`); workspace-authorized provider submission |
| POST | `/stt-review` | Compare cached reference or supplied verified human reference |
| GET | `/stt-review/audio` | Authenticated private recording, available only after retrieval |

`GET /api/v1/runs/RUN_ID` with `X-STT-Review: 1` hydrates the owner's full `evaluation.stt_quality` and `evaluation.report.stt_quality` summary and evidence. Existing report fields remain intact. No model rewrites the report. Normal run detail without this opt-in header excludes the private review.

Comparison body example (replace the hash and timings with actual reviewed evidence):

```json
{
  "recording_scope": "caller_only",
  "scope_confirmed": true,
  "target": "caller_only",
  "bolna_annotations": {
    "source": "bolna",
    "scope": "caller_only",
    "segments": [
      {"text": "I do want a refund", "speaker": "0", "role": "caller", "start": 1.2, "end": 3.8}
    ]
  },
  "human_reference": {
    "source": "human",
    "scope": "caller_only",
    "human_verified": true,
    "verified_by": "Your reviewer identifier",
    "audio_sha256": "REPLACE_WITH_THE_RECORDING_SHA256",
    "segments": [
      {"text": "I do not want a refund", "speaker": "caller", "role": "caller", "start": 1.2, "end": 3.8}
    ]
  }
}
```

This example is synthetic and is not ground truth for any real call. For an automatic cached reference, omit `human_reference` and submit `speaker_roles: {"dg_0":"caller","dg_1":"agent"}` plus `speaker_mapping_confirmed: true` after listening.

## Security and limits

The new recording downloader uses only the authenticated Bolna execution endpoint, validates UUIDs, follows bounded HTTPS redirects, pins public DNS results, blocks private network destinations, strips Bolna credentials across hosts, limits streamed size, and accepts audio media types. It never stores signed recording URLs. This does not retrofit the older live-ingestion recording downloader.

Provider failures are sanitized; response bodies, credentials, signed URLs, and transcript fragments are not included in error messages. Audio and new reference data stay in the private artifact store and are never written to an LLM prompt or search index by this module. Original Bolna transcripts continue to use the existing run storage and retention rules.

The first version supports retained Bolna execution recordings. It cannot recover expired/deleted originals, missing legacy full transcripts, or timestamp metadata never captured. WAV channel count/duration is inspected locally; other audio formats may lack these metadata. The existing Deepgram adapter is configured for English. There is no new provider, fallback, real-time monitoring, automatic human verification, durable worker, cross-instance artifact database, cross-worker deduplication guarantee, or range-streaming audio API. Manual work is bounded by request/provider timeouts; a disconnected browser may need to reload and retry. Successful automatic requests reuse their cached reference. Concurrent preparations in the same backend event loop share one in-flight submission, including its failure result. This is not a distributed job or deduplication guarantee across workers.

## Verification

```bash
.venv/bin/pytest -q tests/test_stt_quality.py tests/test_stt_artifacts.py tests/test_stt_review_api.py tests/test_stt_providers.py
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Tests use synthetic transcripts with known substitutions/deletions/insertions and meaning changes. They cover speaker/time alignment, mismatched coverage, empty references, rates above 100%, missing audio/timings, provider failures, source preservation, workspace-authorized submission, explicit opt-out, automatic preparation, concurrent submission sharing, report reload, recording retries, key scoping, expiry, unsafe redirects and streamed limits. Deterministic provider tests mock network responses. The separate live verification below checks actual services.

A local Chromium check used synthetic speech generated by `espeak` and a synthetic reference fixture: WAV decoding, actual playback, timestamp seeking, partial/no-rate state, estimated-disagreement display, persistence/reload, missing credentials, and a 390px viewport all passed with no page errors or external requests. It was not a live Deepgram evaluation and does not establish STT accuracy. Real-recording retrieval and Deepgram submission have now been verified; see [live STT verification](stt-live-verification.md). No deployment was performed.

## Automatic whole-call alignment (v3)

Complete mixed Bolna conversations can be compared with retained Deepgram output
without inventing original utterance times. Original and reference transcripts are
immutable. A separate alignment object records inferred roles, supporting anchor
word counts and word-correspondence coverage.

Unique four-word phrases within both texts propose each diarization ID's role
relative to Bolna's supplied labels. Each ID needs 12 distinct reference anchor words
and 90% role dominance. Both role streams need anchors in the first and final thirds
of both texts. Diarization numbers have no fixed caller/agent meaning. Unknown or
contradictory roles, repeated ambiguous phrases, caller-only/mixed mismatches, missing
reference timing, hash mismatches, local-only anchors and partial supplied original
timings keep results unscored. Supplied roles/timings are not overwritten. The path
is bounded to 800 words per complete source; it never scores an easy-only subset.

The result is **estimated whole mixed-call transcript disagreement**. All words and
deterministic Levenshtein substitutions/deletions/insertions within each inferred
role contribute. Low agreement itself is not a rejection gate: that would hide poor
STT. Word coverage is a diagnostic, not an accuracy threshold. Input completeness and
correct Bolna role labels remain assumptions tied to the same-call source provenance.

Every finding is Needs review with low, uncalibrated confidence. Verbatim source turns
provide context. Positions derive from reference speech and neighbouring anchors;
the UI labels them **Listen near** and explains the inference. Bolna timings stay
absent. This is text correspondence, not acoustic forced alignment, and never yields
human-verified WER. Shared model errors or wrong original labels can still mislead
the estimate. Meaning-change heuristics remain bounded English rules; Unicode word
support is not Hindi/Hinglish semantic detector validation.

Real provider end-times can extend beyond a WAV's duration. Such segments do not
establish speaker roles or supply finding positions; their words remain in the text
denominator and their provider times are retained unchanged. No timestamps or scores
are clamped. Existing supplied-interval scoring keeps its duration checks.
