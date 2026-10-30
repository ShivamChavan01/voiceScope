# Real Bolna call verification

Verified at 2026-10-25T13:48:40.405577+00:00 against the local working tree.

## What ran

The existing configured Bolna key retrieved the account's agent and four completed executions from its August 19 history. No new phone call was placed and no agent or webhook configuration was changed.

Selected execution: `74c12d45-d85f-4fe2-b5a6-4d48a8d861aa`. Duration: 72.0 seconds.

The full execution payload was fetched from Bolna's Get Execution API and replayed through the actual FastAPI `POST /api/v1/webhooks/call-completed` handler. The run used the configured real Deepgram and Groq services. Database and Chroma paths were isolated under a private temporary directory; production storage was not changed.

## Verified results

| Check | Result |
| --- | --- |
| Bolna agent list, execution list, and Get Execution | HTTP 200 |
| Recording download | Succeeded through the real webhook handler |
| Deepgram STT | Completed; 852 transcript characters |
| Groq analysis and report | Completed using `openai/gpt-oss-120b` |
| Webhook response | HTTP 200 |
| Run ID | `cd1f8afd-e88c-4285-80b0-b224289f5b95` |
| Persisted run reload | HTTP 200 |
| Transcript, report, and harness after reload | Exact matches to the evaluation response |
| Status | `partial` / `needs_review` |
| Pipeline errors | 0 |
| Validation warnings/errors | 3 |

The harness required review because one finding failed heuristic citation matching, the sentiment heuristic disagreed with the model, and the unresolved outcome lacked a recognized evidence marker. These are evaluator warnings, not proof that the voice agent violated company policy. No hallucination was flagged by the model.

## Limits

This is a replay of an actual Bolna execution through local ingestion with real external STT and LLM calls. It does not verify a fresh Bolna-originated POST to the deployed application, automatic retries, durable job processing, event deduplication, or PostgreSQL persistence.

The initial replay exposed dropped source execution/agent metadata. The subsequent speaker-attribution fix now preserves the call ID and parsed agent metadata. Tool-execution evidence was not verified or invented. Semantic accuracy of the model's findings remains separate from successful pipeline execution.

Read-only checks of the deployed frontend proxy still returned 16 Runs, zero calls in the 24-hour monitoring window, and zero benchmark cases. The local fixes have not been deployed.

## Local evidence

Private raw execution, response, logs, isolated database, and replay script are under `/tmp/voicescope-live-qa/`. They are excluded from this committed report because they can contain call data. The replay can be repeated on this machine with:

```bash
.venv/bin/python /tmp/voicescope-live-qa/replay.py
```

Repeating the command uses live provider calls and creates another local run; ingestion is not yet deduplicated. This temporary script is session evidence, not a production worker or a packaged integration test.

## Speaker-attribution follow-up

The same real call was replayed using its Bolna-supplied transcript. Its 20 turns retained explicit Agent/Customer roles and source metadata. A real Chromium browser opened the run and confirmed all 20 labels persisted after a page reload.

The actual recording was also uploaded through the browser and streamed through the real Deepgram/Groq path. It produced 12 diarized turns labeled Agent or Customer with an explicit inferred marker. All labels survived reload and the browser reported no page errors. See [speaker attribution](speaker-attribution.md) for the evidence and uncertainty rules.
