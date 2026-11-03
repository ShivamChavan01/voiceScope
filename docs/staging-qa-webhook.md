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
