# VoiceScope

[![CI](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Voice AI agents hallucinate. Nobody catches it. VoiceScope does.**

Upload a call recording → get a structured report: intent, sentiment, hallucination detection, outcome, and quality metrics. Built-in validation harness catches LLM errors before they reach your dashboard. Supports Deepgram, Gemini, Whisper (STT) and OpenAI, Anthropic, Gemini, Groq, Ollama (LLM) out of the box.

## Features

- **Multi-Provider LLM Support** — OpenAI, Anthropic, Google Gemini, Ollama (local), Mistral
- **3-Stage Agentic Pipeline** — Transcription → Analysis → Report
- **13-Layer Validation Harness** — Catches LLM hallucinations before they reach your dashboard
- **Self-Improvement Loop** — Harness benchmarks itself, auto-tunes weights, gets smarter over time
- **Monitoring & Alerting** — Threshold-based alerts on hallucination rate, escalation rate, quality score
- **QA Cohort System** — Weighted scoring, resolution criteria, pass/fail tracking
- **Custom Extractions** — User-defined post-call analysis schemas (text, boolean, number, category)
- **Content Guardrails** — Harmful content detection + PII redaction
- **Plugin System** — Add custom analysis agents via environment variables
- **Streaming SSE** — Real-time pipeline progress updates
- **Batch Processing** — Analyze multiple files with webhook callbacks
- **Conversation Flow** — Extract speaker turns, interruptions, talk-time ratio
- **Evaluation Metrics** — LLM-as-judge quality scoring
- **Cost Tracking** — Token usage and cost per call across providers
- **Request Tracing** — Correlation IDs and stage timing
- **API Key Auth** — Multi-tenant rate limiting

## Architecture

```
Audio File
    │
    ▼
┌─────────────────────┐
│  Transcription Agent │  ← OpenAI Whisper / Provider-specific STT
│  (audio → text)      │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Analysis Agent     │  ← Configurable LLM + RAG (ChromaDB)
│  intent / sentiment  │
│  hallucination       │
│  outcome / escalation│
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    Report Agent      │  ← Configurable LLM structured output
│  quality score       │
│  findings + recs     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Flow Agent (opt)   │  ← Speaker turns, talk-time ratio
│   Eval Agent (opt)   │  ← LLM-as-judge scoring
└─────────────────────┘
    │
    ▼
Structured JSON Report
```

## Validation Harness

Every LLM output passes through 13 validation layers before reaching your dashboard:

| # | Layer | What It Catches |
|---|-------|-----------------|
| 1 | Schema Validation | Wrong types, bad enums, missing fields |
| 2 | Citation Verification | Findings not grounded in transcript |
| 3 | Cross-Check | Analysis disagrees with itself |
| 4 | Fact Extraction | Numbers, dates, promises contradict transcript |
| 5 | Sentiment Consistency | "Angry" transcript labeled "positive" |
| 6 | Outcome Evidence | "Resolved" with no resolution proof |
| 7 | Escalation Verification | "Escalated" with no manager mention |
| 8 | Response Time Monitoring | LLM taking 10x longer than usual |
| 9 | Token Tracking | Abnormal token usage |
| 10 | Duplicate Detection | Same analysis repeated within 5 min |
| 11 | Audio Quality Pre-Check | Garbage, silent, or too-short audio |
| 12 | Confidence Calibration | Tracks if confidence matches accuracy |
| 13 | Feedback Loop | Users mark correct/incorrect |

Every API response includes a `harness` field:

```json
{
  "harness": {
    "truth_score": 0.87,
    "confidence": "high",
    "validation_errors": [],
    "layer_scores": { "schema": 1.0, "citations": 0.92, "facts": 0.95 }
  }
}
```

## Self-Improvement Loop

VoiceScope gets smarter every time you run the loop:

```
Labeled Test Data → Benchmark → Compare vs Expected → Optimize Weights → Track Failures → Next Run Is Better
```

```bash
# Run one improvement cycle
curl -X POST http://localhost:8000/api/v1/loop/run \
  -H "X-API-Key: your-api-key"

# Check current weights and suggestions
curl http://localhost:8000/api/v1/loop/status \
  -H "X-API-Key: your-api-key"
```

## Monitoring & Alerting

```bash
# Get metrics dashboard
curl http://localhost:8000/api/v1/monitoring/metrics \
  -H "X-API-Key: your-api-key"

# Create alert rule
curl -X POST http://localhost:8000/api/v1/monitoring/alerts \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High hallucination rate",
    "metric": "hallucination_rate",
    "comparator": "gt",
    "threshold": 0.3,
    "window_minutes": 60
  }'
```

## QA Cohort System

```bash
# Create a QA cohort
curl -X POST http://localhost:8000/api/v1/qa/cohorts \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales QA",
    "platform_filter": "vapi",
    "criteria": [
      {"name": "resolved", "description": "Was the issue resolved?", "weight": 2.0},
      {"name": "polite", "description": "Was the agent polite?", "weight": 1.0}
    ]
  }'

# Score a call
curl -X POST http://localhost:8000/api/v1/qa/cohorts/1/score \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "call-001", "metrics": {"quality_score": 85, "outcome": "resolved"}}'
```

## Content Guardrails

```bash
# Check for harmful content
curl -X POST http://localhost:8000/api/v1/guardrails/check \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to kill myself", "check_type": "input"}'

# Redact PII
curl -X POST http://localhost:8000/api/v1/guardrails/check \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Email john@example.com", "check_type": "redact_pii"}'
```

## Quick Start

```bash
git clone https://github.com/ShivamChavan01/voicescope
cd voicescope

cp .env.example .env
# Configure your LLM provider keys in .env

pip install -r requirements.txt
uvicorn main:app --reload
```

## Configuration

Set your LLM provider in `.env`:

```bash
# Options: openai, anthropic, gemini, ollama, mistral
LLM_PROVIDER=openai

# Provider API keys (only need the one you're using)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
MISTRAL_API_KEY=...

# For local Ollama
OLLAMA_BASE_URL=http://localhost:11434
```

## Usage

### Single Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "X-API-Key: your-api-key" \
  -F "file=@call_recording.mp3"
```

### Streaming (SSE)

```bash
curl -N -X POST http://localhost:8000/api/v1/analyze/stream \
  -H "X-API-Key: your-api-key" \
  -F "file=@call_recording.mp3"
```

### Batch Processing

```bash
curl -X POST http://localhost:8000/api/v1/batch \
  -H "X-API-Key: your-api-key" \
  -F "files=@call1.mp3" \
  -F "files=@call2.mp3" \
  -F "callback_url=https://your-webhook.com/callback"
```

### Cost Summary

```bash
curl http://localhost:8000/api/v1/costs \
  -H "X-API-Key: your-api-key"
```

### Webhook Integration

VoiceScope receives call-completed webhooks from **8 voice AI platforms** with automatic payload detection.

**Endpoint:** `POST /api/v1/webhooks/call-completed`

#### Supported Platforms

| Platform | Detection Signal | Recording Source | Region |
|---|---|---|---|
| **Vapi** | `message.type: "end-of-call-report"` | `artifact.recording.monoUrl` | Global |
| **Retell** | `event: "call_ended"` | `call.recording_url` | Global |
| **Bland.ai** | `concatenated_transcript` or `transcripts[]` | `recording_url` | Global |
| **Bolna** | `telephony_data` object | `telephony_data.recording_url` | India (YC F25) |
| **Synthflow** | `collected_variables` or `executed_actions` | *(via API)* | Global |
| **Air.ai** | `call.sid` + `call.callRecordingUrl` | `call.callRecordingUrl` | Global |
| **Generic** | any `call_id` + `recording_url` | `recording_url` | Any |

#### Vapi

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "end-of-call-report",
      "endedReason": "hangup",
      "call": {
        "id": "7420f27a-30fd-4f49-a995-5549ae7cc00d",
        "status": "ended",
        "recordingUrl": "https://storage.vapi.ai/recording.mp3"
      },
      "artifact": {
        "recording": {"monoUrl": "https://storage.vapi.ai/mono.mp3"},
        "transcript": "AI: How can I help? User: I need a refund."
      }
    }
  }'
```

#### Retell

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "event": "call_ended",
    "call": {
      "call_id": "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6",
      "recording_url": "https://retellai.s3.us-west-2.amazonaws.com/recording.wav",
      "transcript": "Agent: Hi! User: I need help.",
      "duration_ms": 15791,
      "disconnection_reason": "user_hangup"
    }
  }'
```

#### Bland.ai

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "12345678-1234-1234-1234-123456789012",
    "completed": true,
    "concatenated_transcript": "user: Hello?\nassistant: This is a test call.",
    "corrected_duration": "11",
    "recording_url": "https://api.twilio.com/Recordings/RE456",
    "from": "+15559876543",
    "to": "+15551234567"
  }'
```

#### Bolna (India, YC F25)

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "id": 7432382142914,
    "agent_id": "3c90c3cc-0d44-4b50-8888-8dd25736052a",
    "status": "completed",
    "conversation_duration": 123,
    "transcript": "Agent: Hello! User: Check my order.",
    "telephony_data": {
      "recording_url": "https://bolna-recordings.s3.amazonaws.com/rec.mp3",
      "from_number": "+1987654007",
      "to_number": "+10123456789"
    }
  }'
```

#### Synthflow

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "agent_goodbye",
    "duration": 113,
    "transcript": "\nbot: Hey!\nhuman: Hi, I need help.",
    "collected_variables": {"user_name": {"value": "Julian", "collected": true}}
  }'
```

#### Air.ai

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "Content-Type: application/json" \
  -d '{
    "call": {
      "sid": "CAec7g2x30425ba039a83ffb4286754983",
      "callRecordingUrl": "https://api.twilio.com/Recordings/RE25a9z",
      "transcript": "BOT: Hey Tyler!\nHUMAN: How's it going?",
      "duration": 44,
      "outcome": "Booked appointment"
    }
  }'
```

#### Custom / Other Platforms

Any payload with `call_id` + `recording_url` fields is accepted as a generic webhook:

```bash
curl -X POST https://your-voicescope.com/api/v1/webhooks/call-completed \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "call.ended",
    "call_id": "custom-001",
    "recording_url": "https://your-cdn.com/calls/custom-001.mp3"
  }'
```

#### Security

All webhook URLs are validated:
- **HTTPS-only** — HTTP URLs are rejected
- **Private IP blocking** — DNS resolution checked against private/link-local ranges
- **Content-type verification** — downloaded file must be `audio/*`

> **Note:** Webhook signature verification (Vapi API key / Retell `x-retell-signature` / Synthflow HMAC-SHA256) is a next step for production hardening.

## Python SDK

```python
from sdk.voicescope import VoiceScope

client = VoiceScope(api_key="your-key", base_url="http://localhost:8000")

# Single analysis
report = await client.analyze("call.mp3")
print(report.report.quality_score)

# Batch
result = await client.analyze_batch(["call1.mp3", "call2.mp3"])
```

## Plugin System

Create a custom analysis agent:

```python
from agents.base import BaseAgent
from agents.registry import AgentRegistry

@AgentRegistry.register
class ComplianceAgent(BaseAgent):
    name = "compliance"
    description = "Checks for compliance violations"

    async def run(self, ctx, **kwargs):
        # Your analysis logic here
        ctx.report["compliance"] = {"passed": True}
        ctx.mark_stage("compliance")
        return ctx
```

Enable it:

```bash
PLUGIN_AGENTS=examples.custom_agent
```

## Sample Response

```json
{
  "run_id": "abc-123",
  "generated_at": "2026-06-17T06:00:00",
  "provider": {
    "name": "openai",
    "model": "gpt-4o",
    "cost_usd": 0.00234,
    "input_tokens": 1500,
    "output_tokens": 800
  },
  "transcript_meta": {
    "language": "english",
    "duration_seconds": 120.5,
    "char_count": 1840
  },
  "analysis": {
    "intent": "Customer wants to cancel subscription",
    "sentiment_arc": "negative",
    "hallucination_detected": false,
    "outcome": "resolved",
    "escalation_signal": false
  },
  "report": {
    "executive_summary": "Customer called to cancel but was retained after agent offered a discount.",
    "quality_score": 82,
    "key_findings": ["Agent handled objection well", "Response time was slow"],
    "recommendations": ["Reduce hold time", "Proactively offer retention deals earlier"]
  },
  "conversation_flow": {
    "total_turns": 12,
    "interruptions": 2,
    "talk_time_ratio": {"Agent": 0.45, "Customer": 0.55}
  },
  "evaluation": {
    "analysis_quality_score": 4,
    "confidence_score": 0.87
  }
}
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/api/v1/health` | GET | Health check |
| `/api/v1/analyze` | POST | Analyze single audio file |
| `/api/v1/analyze/stream` | POST | Stream analysis via SSE |
| `/api/v1/batch` | POST | Batch analyze multiple files |
| `/api/v1/batch/{id}` | GET | Check batch status |
| `/api/v1/batch/{id}/results` | GET | Get batch results |
| `/api/v1/costs` | GET | Cost summary |
| `/api/v1/webhooks/call-completed` | POST | Receive voice AI webhooks |
| `/api/v1/harness/status` | GET | Validation harness state |
| `/api/v1/harness/feedback` | POST | Submit correct/incorrect feedback |
| `/api/v1/harness/calibration` | GET | Confidence calibration report |
| `/api/v1/loop/run` | POST | Run self-improvement cycle |
| `/api/v1/loop/status` | GET | Loop weights and suggestions |
| `/api/v1/loop/benchmark` | GET | Latest benchmark results |
| `/api/v1/loop/suggestions` | GET | Prompt improvement suggestions |
| `/api/v1/loop/weights` | GET | Current layer weights |
| `/api/v1/monitoring/metrics` | GET | Monitoring dashboard |
| `/api/v1/monitoring/alerts` | GET/POST/DELETE | Alert rules CRUD |
| `/api/v1/monitoring/incidents` | GET | Triggered incidents |
| `/api/v1/monitoring/check` | POST | Check alert rules |
| `/api/v1/qa/cohorts` | GET/POST | QA cohort management |
| `/api/v1/qa/cohorts/{id}/score` | POST | Score a call |
| `/api/v1/qa/cohorts/{id}/results` | GET | Cohort results |
| `/api/v1/extractions/schemas` | GET/POST | Extraction schema management |
| `/api/v1/extractions/schemas/{id}/run` | POST | Run extractions |
| `/api/v1/extractions/schemas/{id}/results` | GET | Extraction results |
| `/api/v1/guardrails/status` | GET | Guardrail status |
| `/api/v1/guardrails/check` | POST | Check content safety |

## Deploy

### Docker

```bash
docker build -t voicescope .
docker run -p 8000:8000 --env-file .env voicescope
```

### Docker Compose

```bash
docker compose up -d
```

### Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
