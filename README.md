# VoiceScope

[![CI](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Open source observability API for voice AI agents. Multi-provider LLM support, plugin system, and comprehensive analytics.

Upload a call recording → get a structured JSON report covering intent, sentiment, hallucination detection, outcome, conversation flow, and quality metrics.

## Features

- **Multi-Provider LLM Support** — OpenAI, Anthropic, Google Gemini, Ollama (local), Mistral
- **3-Stage Agentic Pipeline** — Transcription → Analysis → Report
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

VoiceScope can receive call-completed webhooks from voice AI platforms (Vapi, Retell, etc.) for automatic pipeline processing:

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/call-completed \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "call.ended",
    "call_id": "abc-123",
    "recording_url": "https://cdn.example.com/recordings/abc-123.mp3",
    "metadata": {"agent_id": "agent_001"}
  }'
```

**Payload:**

| Field | Type | Description |
|---|---|---|
| `event` | string | Must be `"call.ended"` |
| `call_id` | string | Unique call identifier |
| `recording_url` | string | HTTPS URL to fetch the audio recording |
| `metadata` | dict | Optional platform-specific extra fields |

The endpoint validates the payload, downloads the recording (SSRF-protected via HTTPS-only + DNS resolution blocking), runs it through the full 3-stage pipeline, and returns the analysis report.

> **Note:** This is built and tested with mocked payloads matching Vapi/Retell-style schemas. Full certification with live platform accounts is a next step.

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
