# Private single-company deployment

VoiceScope serves one company's trusted operators. There are no separate company
accounts or per-operator permission levels. Every authenticated operator can access
the company's calls, policies and reports. API-key hashing partitions STT artifacts;
it is not user authorization.

## Frontend access

The existing Next.js frontend now requires standard HTTP Basic authentication for
pages, assets and API requests. There is no account database, signup, password reset
or custom login protocol. Browsers supply the standard authentication dialog.
Use a secret manager or private process environment to configure:

- `OPERATOR_AUTH_USER`: the private operator name, without a colon.
- `OPERATOR_AUTH_PASSWORD`: a randomly generated secret of at least 24 characters.
- `BACKEND_URL`: the private backend origin.
- `API_KEY`: a backend key matching `VALID_API_KEYS`, retained on the server.

No values belong in `NEXT_PUBLIC_*` variables, Git, URLs or frontend static files.
The frontend returns 503 when operator credentials are absent or too short. All
visitors require valid Basic credentials; enabling STT is not an authentication
bypass. A second access check runs inside the API handler independently of Next's
Proxy. Cross-origin API/subresource and unsafe requests are rejected. Normal
top-level read navigation from an operator link or identity-provider redirect still
requires authentication. Framing is denied. Private data is not cached.

Use HTTPS outside loopback. Plain HTTP is accepted only for `localhost`, `127.0.0.1`
and IPv6 loopback; it is rejected for other request origins. The reverse proxy must
preserve the actual HTTPS scheme and host. Do not make a self-hosted frontend port
public behind an incorrectly configured HTTP forwarding layer. Verify the external
URL after configuration. Basic credentials remain cached by the browser; close the
private browser session to stop using them. This is not individual operator session
management or enterprise identity. No such capability is claimed.

`STT_REVIEW_PROXY_ENABLED` defaults to false. Enable it only on the authenticated,
private frontend. Keep backend `VALID_API_KEYS` configured independently. Private
run/recording routes require a backend key even when the frontend is inaccessible.

## Bolna webhook boundary

Configure a separate backend `BOLNA_WEBHOOK_SECRET` securely, then use Bolna's
**Add headers** setting to send `X-Webhook-Key` with that value to the backend's
HTTPS `POST /api/v1/webhooks/call-completed` endpoint. The secret authenticates
only that POST route and only Bolna-shaped events. It cannot read runs, recordings
or policies. Do not send webhooks through the browser-authenticated frontend.
The existing `X-API-Key` operator path remains available for controlled replay.

[Bolna's webhook guide](https://www.bolna.ai/docs/post-call/polling-call-status-webhooks)
documents custom headers and source IPs. This implementation authenticates a shared
header secret; it does not claim verification of a provider HMAC signature. Protect
the secret, use TLS and verify an actual Bolna-originated delivery before declaring
the hosted integration working. No agent or webhook configuration was changed by
this review.

Completed Bolna events are deduplicated by execution ID using private SQLite
receipts on `DATA_DIR`. A completed replay returns its persisted report. A concurrent
attempt returns 409 with `Retry-After`. Failures release the claim so another attempt
can retry. Reports must exist before completion is acknowledged. In-progress claims
expire after ten minutes to recover from process crashes.

This is not exactly-once provider execution: a crash after a provider call but before
the receipt is saved can repeat that work after the lease expires. Keep one private
deployment volume shared by all workers; independent replica filesystems cannot
coordinate. There is no durable background queue, first-delivery backfill of old
receipts, or automatic re-evaluation of changed payloads after a completed receipt.
Deleting a report retains its completed receipt; a later replay returns an
actionable 409 rather than silently recreating the deleted evaluation.
The receipt stores execution/run IDs and lease metadata, not audio or transcripts.

## Storage, backups and rollback

Use a writable private persistent `DATA_DIR`; retain its owner permissions. The
non-root Docker process starts with umask 077. STT artifacts expire 24 hours after
their last write and are cleaned on access. Primary run/transcript and webhook
receipt retention is separate. The private deployment operator must choose that
retention period and include receipts in normal report backup/restore procedures.
Verify existing `DATA_DIR` and explicit database paths before adopting the Docker
default. Migrate any database outside `/app/data` through an approved backup and
restore procedure rather than starting with an unintended empty directory.

Before deployment, verify a recent backup and perform a restore rehearsal against
an isolated directory/database. Use SQLite's online backup operation for live
SQLite files; do not copy only a live `.db` file while ignoring its WAL. Include
primary reports, policy/knowledge data and webhook receipts. Decide explicitly
whether short-lived STT audio should be excluded from backups.

Record the current frontend deployment, backend image digest, environment variable
names and volume/database bindings before changing a release. Roll back code by
promoting the recorded previous frontend and backend artifacts; do not overwrite
the current data volume with an old snapshot unless a data restore is explicitly
approved. Test health, authentication and persisted-run access after rollback.
The new receipt table is additive; the old application does not consume it.

The observed historical frontend deployments do not contain the new operator gate.
They are not safe rollback targets on an unrestricted production domain. Establish
independent private access that survives rollback, or verify an authentication-preserving
baseline before deploying. Do not assume that a Ready deployment is a secure rollback.

These are deployment instructions, not proof of a production backup or rollback.
The release report identifies what was actually tested locally and what hosting
access is still missing. No production backup, deployment or restore was executed.
