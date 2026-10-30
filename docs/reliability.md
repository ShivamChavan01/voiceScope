# Evidence review

VoiceScope checks explicit transcript statements against configured company rules. It does not observe the customer's refund system. A completion claim without an action result remains unverified; absence of a tool log never proves failure.

## Configure and reproduce

1. Start the backend and frontend using the README setup.
2. Open Settings → Policies. Add an actual company rule using one of the supported templates below. Rules are opt-in; bundled reference knowledge is model context only.
3. Evaluate an attributed transcript or ingest a completed Bolna execution. Existing runs are not automatically re-evaluated when policies change.
4. Open Runs → Findings. Inspect the quote, applied policy snapshot, severity, and explanation. Select the turn link to inspect its transcript context.
5. For a credential-free demo, select **Explore 3 synthetic scenarios** on Overview. These use fictional policies attached only to their own evaluations.

| Supported check | Accepted template | Observed behavior required |
| --- | --- | --- |
| `no_same_day_refund_guarantee` | Agents must never guarantee same-day refunds. | An explicit same-day refund guarantee |
| `honor_escalation_request` | If a customer requests a supervisor, agents must honor the request immediately. | An explicit customer request followed by an explicit refusal |

The detector supports bounded English wording. It rejects contradictory or unrelated rule text instead of guessing its meaning. Conditional business exceptions and arbitrary prose require further implementation. It does not infer a failed transfer from an absent transfer log.

## Stored contract

`evaluation.reliability` has schema version `1`, a status (`assessed` or `insufficient_evidence`), checked rule IDs, immutable policy snapshots, findings, and limitations. Each finding contains category, status, severity, title, explanation, exact evidence quotes with zero-based transcript turn indices, optional policy ID, and missing evidence.

- `policy_violation` with `confirmed`: an explicit supported pattern with transcript-labeled roles contradicts the configured rule.
- `policy_violation` with `needs_review`: matching wording has inferred or uncertain attribution.
- `unverified_claim`: refund completion is asserted, but no action result is available.
- `insufficient_evidence`: a required transcript or attribution is unavailable.

No enabled policies produces an insufficient-evidence assessment, even when there are no findings. No matches in supported checks never means the whole call is compliant. These deterministic findings survive a later model failure and are persisted with the evaluation. Historical records without this contract display **Not assessed**.

Policies are stored in SQLite at `POLICY_DB_PATH`, falling back to `DATA_DIR/policies.db`. The current store and API are single-workspace; frontend authentication and tenant isolation remain open.

## API

Use the configured backend API authentication header; keep credentials in local environment configuration.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/policies/rules` | List configured rules |
| POST | `/api/v1/policies/rules` | Create/update `{id,title,kind,text,enabled}`; incompatible text returns 422 |
| DELETE | `/api/v1/policies/rules/{id}` | Remove a rule |
| POST | `/api/v1/demo/reliability` | Seed three reproducible synthetic scenarios without activating real policies |

## Speech diagnostics

Stored Bolna diagnostics expose reported first-audio latency, mean transcription/LLM/synthesis timings, interruptions, and call-ending information when present. Transcription uses the last event per conversation turn; LLM and synthesis use reported first-token timings, excluding welcome-turn measurements. Component means are not summed into an invented end-to-end latency. Missing measurements stay unavailable; measured zero remains zero.

These observations can help investigate delay. They do not establish network failure, transcription accuracy, or a repair performed during a live call. VoiceScope currently inspects calls after completion.

## Verification and limits

An existing real completed Bolna execution was fetched with configured credentials and replayed through the local webhook, evaluated with the live provider, persisted, and inspected after reload. The new assessment correctly reported insufficient evidence with no configured policies. Its provider diagnostics included approximately 136 ms first audio, 470 ms mean LLM timing, and three interruptions. These are observations from one historical call, not benchmark results.

The three synthetic scenarios, role uncertainty, negation, unrelated refusals, conditional promises, contradictory policies, missing measurements, policy CRUD, model failure persistence, and real/demo aggregation have regression coverage. Desktop/mobile browser checks exercise quote navigation and policy configuration. Fresh provider-originated webhook delivery, durable deduplication/retries, external action verification, multilingual detection, and production access control remain unfinished. See the original [audit](p0-audit.md) and [live-service report](bolna-verification.md).
