# Authorized Bolna QA calls on free staging

Default synthetic-only staging behavior is unchanged. An explicit
`STAGING_QA_AGENT_ID` UUID enables an additional authenticated post-call path for
that agent only. These are real operator-authorized test calls, not synthetic
fixtures or measured recognizer accuracy. They are publicly viewable through the
read-only demo frontend by operator choice; do not use this mode for customer calls.

Keep `STAGING_DEMO_ONLY=true` and `PUBLIC_SYNTHETIC_DEMO=true`. Set the separate
`BOLNA_WEBHOOK_SECRET` (at least 24 characters, different from every operator key)
and server-side `BOLNA_API_KEY` for recording retrieval. All independent STT and
LLM provider credentials remain forbidden. No external database is allowed.

Configure **only the isolated QA agent** to deliver completed-call payloads to
`https://voicescope-staging-demo.onrender.com/api/v1/webhooks/call-completed`
with an `X-Webhook-Key` header containing the secret. This header authenticates a
shared secret; it is not a cryptographic signature over the payload.

The handler verifies the agent and execution UUID, preserves the original Bolna
transcript, derives speaker roles only from its supplied labels, runs the existing
configured deterministic policy checks, and retrieves audio from Bolna's stable
execution recording endpoint. Payload-provided recording URLs are ignored. The
existing DNS-pinned, bounded downloader strips credentials across redirects.
No new transcription, model evaluation or phone calls are triggered.

Reports explicitly describe the restricted evaluation scope. Missing independent
references, trustworthy utterance timing and channel coverage remain **Not scored**.
Provider latency/interruption diagnostics are not independently verified findings.
Phone numbers, signed recording URLs and complete raw execution logs are not copied
into the public report. The supplied transcript and recording can themselves contain
personal information: use only test data approved for public display.

Successful acknowledgement requires saved audio, report and webhook receipt. A
recording failure saves a partial transcript report, returns 503 and releases the
receipt for retry. Duplicate completed deliveries reuse the saved report without
another recording fetch. In-flight duplicates return 409. Delivery is at least once;
independent SQLite stores do not provide a distributed exactly-once transaction.

Render Free storage is **ephemeral**. Normal restarts on the same filesystem retain
records, but replacement/deploy can erase calls and receipts. Synthetic fixtures
reseed; real calls do not. Replay the authorized executions after replacement when
needed. Audio artifacts expire after 24 hours and then return 404. A duplicate report
acknowledgement does not refresh expired audio. Do not claim durable real-call storage.

The public proxy cannot forward a webhook credential. Public uploads, edits, policy
changes, deletions, recording retrieval requests and independent STT submissions
remain blocked. Removing `STAGING_QA_AGENT_ID` restores synthetic-only behavior; if
QA records remain on disk, startup fails safely instead of silently publishing them
under a synthetic-only configuration. Do not delete unrelated data to bypass this.

Deploy the verified backend commit and opt in only on the existing free staging
service. The existing frontend remains read-only; no frontend API contract changes
are required. Keep the original production agent and production service unchanged.

## Optional paid Deepgram reference preparation

After operator authorization, `STAGING_QA_DEEPGRAM=true` permits the server-side
`DEEPGRAM_API_KEY` for this agent's post-call references only. LLM keys and other
transcription providers remain forbidden. Set `DEEPGRAM_MODEL=nova-3` and
`DEEPGRAM_LANGUAGE=multi` for the authorized English/Hindi test recordings.
The normal provider defaults remain Nova-2/English outside this configuration.

When enabled, QA ingestion prepares a reference from the saved original recording
through the existing STT service. Successful references are reused; duplicate
webhooks and public page views do not submit another transcription. Provider failures
are reported separately and do not invent a rate or discard the primary call report.
The primary configured staging operator API key owns the reference cache.

The existing POST `/api/v1/runs/{execution_id}/stt-review/reference` can be used for
operator preparation/retry with **both** the operator API key and the separate
`X-Webhook-Key`. It accepts only a saved QA call from the configured agent. The public
frontend does not forward that webhook secret, so anonymous visitors still cannot
trigger charges, upload audio or mutate shared data. No public operator control is enabled.

Independent transcription does not establish caller identity or Bolna utterance
timings. Deepgram diarization IDs remain unassigned until evidence establishes roles.
Missing coverage/roles/timing still produces Not scored. The reference text and its
actual audio timestamps are available for listening and review; they are not silently
copied into the original transcript as Bolna timestamps. No reference is declared
human verified. A free-instance replacement can erase the reference cache, so replaying
after replacement can incur another submission. Do not claim exactly-once billing.
