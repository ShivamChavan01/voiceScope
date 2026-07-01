# VoiceScope Webhook Integration — End-to-End Flow

## How It Works

When a call ends on any voice AI platform (Vapi, Retell, Bland, Bolna, Synthflow, Air.ai, or any custom platform), the platform sends a webhook to VoiceScope. VoiceScope auto-detects the platform, downloads the recording, runs the 3-stage analysis pipeline, and returns a structured report.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VOICE AI PLATFORM                                 │
│  (Vapi / Retell / Bland / Bolna / Synthflow / Air.ai / Generic)    │
│                                                                     │
│  Call ends → Platform generates webhook payload with:               │
│    • recording_url (HTTPS link to audio file)                       │
│    • call_id, transcript, duration, metadata                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ POST /api/v1/webhooks/call-completed
                           │ Body: platform-specific JSON payload
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VOICESCOPE API                                    │
│                                                                     │
│  1. AUTO-DETECT PLATFORM (api/schemas.py:441-489)                  │
│     ┌──────────────────────────────────────────────────────┐       │
│     │ Vapi?      → parse_vapi_webhook()                    │       │
│     │ Retell?    → parse_retell_webhook()                  │       │
│     │ Bland?     → parse_bland_webhook()                   │       │
│     │ Bolna?     → parse_bolna_webhook()                   │       │
│     │ Synthflow? → parse_synthflow_webhook()               │       │
│     │ Air.ai?    → parse_airai_webhook()                   │       │
│     │ Unknown?   → parse_generic_webhook() (universal)     │       │
│     └──────────────────────────────────────────────────────┘       │
│                                                                     │
│  2. VALIDATE                                                       │
│     • Event type must be "completed" variant                       │
│     • recording_url must exist                                      │
│     • URL must be HTTPS (SSRF protection)                          │
│     • DNS resolution check (blocks private IPs)                    │
│                                                                     │
│  3. DOWNLOAD RECORDING                                              │
│     • httpx.AsyncClient downloads audio from recording_url          │
│     • Validates content-type starts with "audio/"                   │
│                                                                     │
│  4. RUN PIPELINE (core/pipeline.py)                                │
│     ┌──────────────────────────────────────────────────────┐       │
│     │ Stage 1: TranscriptionAgent                           │       │
│     │   audio → OpenAI Whisper → raw_transcript             │       │
│     │                                                       │       │
│     │ Stage 2: AnalysisAgent                                │       │
│     │   transcript → RAG (ChromaDB) + KB + LLM →           │       │
│     │   intent, sentiment_arc, hallucination_detected,      │       │
│     │   outcome, escalation_signal                          │       │
│     │                                                       │       │
│     │ Stage 3: ReportAgent                                  │       │
│     │   analysis → LLM → quality_score, key_findings,       │       │
│     │   recommendations                                     │       │
│     └──────────────────────────────────────────────────────┘       │
│                                                                     │
│  5. RETURN REPORT                                                   │
│     { platform, call_id, pipeline_result: { run_id, report, ... }} │
└─────────────────────────────────────────────────────────────────────┘
```

## Platform-Specific Payload Examples

### Vapi
```json
{
  "message": {
    "type": "end-of-call-report",
    "call": { "id": "7420f27a-...", "recordingUrl": "https://..." },
    "artifact": {
      "recording": { "monoUrl": "https://..." },
      "transcript": "Agent: Thank you for calling..."
    }
  }
}
```

### Retell
```json
{
  "event": "call_ended",
  "call": {
    "call_id": "Jabr9TXYY...",
    "recording_url": "https://...",
    "transcript": "Agent: Hi, how are you?",
    "duration_ms": 15791
  }
}
```

### Bland.ai
```json
{
  "call_id": "12345678-...",
  "concatenated_transcript": "user: Hello?\nassistant: Test call.",
  "recording_url": "https://...",
  "corrected_duration": "11"
}
```

### Bolna
```json
{
  "id": 7432382142914,
  "status": "completed",
  "transcript": "Agent: Hello! User: Check my order.",
  "telephony_data": { "recording_url": "https://..." }
}
```

### Synthflow
```json
{
  "call_id": "550e8400-...",
  "status": "agent_goodbye",
  "recording_url": "https://...",
  "transcript": "bot: Hey!\nhuman: Hi.",
  "collected_variables": {},
  "executed_actions": {}
}
```

### Generic (any unknown platform)
```json
{
  "call_id": "custom-001",
  "recording_url": "https://...",
  "transcript": "Agent: Hello. User: Hi.",
  "event": "call.ended"
}
```

## What VoiceScope Adds That Platforms Don't

| Feature | Vapi | Retell | Bland | Bolna | Synthflow | VoiceScope |
|---------|------|--------|-------|-------|-----------|------------|
| Works across ALL platforms | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Hallucination detection | ❌ | ⚠️ Enterprise | ⚠️ Enterprise | ❌ | ⚠️ LLM-as-judge | ✅ Every call |
| Knowledge base fact-checking | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Conversation flow analysis | ❌ | ⚠️ Basic | ⚠️ Pathway only | ❌ | ⚠️ Steps only | ✅ |
| Sentiment arc (trajectory) | ❌ | ⚠️ Binary | ⚠️ Single score | ❌ | ⚠️ Binary | ✅ Full arc |
| Self-hosted / open source | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-LLM provider | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 5 providers |
| Plugin system | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Cost tracking per call | ⚠️ Platform only | ⚠️ Platform only | ⚠️ Platform only | ⚠️ Basic | ❌ | ✅ Cross-platform |
| Quality score + recs | ⚠️ Custom rubric | ⚠️ Custom | ⚠️ Enterprise | ❌ | ⚠️ Custom | ✅ Built-in |
