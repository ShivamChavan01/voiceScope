# VoiceScope

[![CI](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Voice AI agents hallucinate. Nobody catches it. VoiceScope does.**

Upload a call recording, get a structured report with intent, sentiment, hallucination detection, outcome, and quality metrics. A 7-layer validation harness catches LLM errors before they reach your dashboard — deterministic rules, not another LLM call. Supports Deepgram, Gemini, Whisper (STT) and OpenAI, Anthropic, Gemini, Groq, Ollama (LLM).

## Features

- **Multi-Provider LLM** — OpenAI, Anthropic, Google Gemini, Groq (free), Ollama (local), Mistral
- **3-Stage Agentic Pipeline** — Transcription → Analysis → Report with speaker classification
- **7-Layer Validation Harness** — Catches hallucinations via schema, citations, facts, sentiment, outcome, escalation, and duplicate checks
- **Self-Improvement Loop** — Benchmarks itself, auto-tunes weights, tracks failures over time
- **Monitoring & Alerting** — Threshold-based alerts on hallucination rate, escalation rate, quality score
- **QA Cohort System** — Weighted scoring, resolution criteria, pass/fail tracking
- **Custom Extractions** — User-defined post-call analysis schemas (text, boolean, number, category)
- **Content Guardrails** — Harmful content detection + PII redaction
- **Streaming SSE** — Real-time pipeline progress updates
- **Batch Processing** — Analyze multiple files with webhook callbacks
- **Cost Tracking** — Token usage and cost per call across providers
- **Webhook Integration** — Auto-detects 7 voice AI platforms (Vapi, Retell, Bland.ai, Bolna, Synthflow, Air.ai, generic)

## Validation Harness

Every LLM output passes through 7 validation layers before reaching your dashboard:

| # | Layer | What It Catches | Weight |
|---|-------|-----------------|--------|
| 1 | Schema Validation | Wrong types, bad enums, missing fields | 0.30 |
| 2 | Citation Verification | Findings not grounded in transcript | 0.15 |
| 3 | Fact Extraction | Numbers, dates, promises contradict transcript | 0.15 |
| 4 | Sentiment Consistency | "Angry" transcript labeled "positive" | 0.10 |
| 5 | Outcome Evidence | "Resolved" with no resolution proof | 0.10 |
| 6 | Escalation Verification | "Escalated" with no manager mention | 0.05 |
| 7 | Duplicate Detection | Same analysis repeated within 5 min | 0.05 |

**Truth Score** = weighted average of all layer scores (0.0–1.0). Every API response includes a `harness` field with `truth_score`, `confidence`, `layer_scores`, and `validation_errors`.

## Quick Start

```bash
git clone https://github.com/ShivamChavan01/voicescope && cd voicescope
cp .env.example .env    # set your API keys
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000/docs for the interactive API.

## Configuration

Set your LLM provider in `.env`:

```bash
# Providers: openai, anthropic, gemini, groq, ollama, mistral
LLM_PROVIDER=groq

# API keys (only need the one you're using)
GROQ_API_KEY=gsk_...           # Free tier: llama-3.3-70b-versatile
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# STT providers (auto-detected)
DEEPGRAM_API_KEY=...           # Nova-2 with diarization ($200 free credits)

# Auth (required — server returns 503 if not set)
VALID_API_KEYS=your-key-1,your-key-2
```

| Provider | Default Model | Cost |
|----------|---------------|------|
| Groq | `llama-3.3-70b-versatile` | Free tier |
| OpenAI | `gpt-4o` | $2.50/$10.00 per 1M tokens |
| Anthropic | `claude-sonnet-4` | $3.00/$15.00 per 1M tokens |
| Gemini | `gemini-1.5-pro` | $1.25/$5.00 per 1M tokens |
| Ollama | `llama3.1` | Free (local) |

## How It Works

```
Audio File
    │
    ▼
┌─────────────────────┐
│  TranscriptionAgent │  ← Deepgram Nova-2 / Gemini / Whisper
│  (audio → text)      │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   AnalysisAgent     │  ← Configurable LLM + RAG (ChromaDB)
│  intent / sentiment  │
│  hallucination       │
│  outcome / escalation│
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    ReportAgent      │  ← Configurable LLM structured output
│  quality score       │
│  findings + recs     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Validation Harness │  ← 7-layer rule-based checks
│  truth_score         │
│  confidence + errors │
└─────────────────────┘
    │
    ▼
  Structured JSON Report
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analyze` | POST | Upload audio → full pipeline analysis |
| `/api/v1/analyze/stream` | POST | SSE streaming analysis |
| `/api/v1/runs` | GET | List analyzed calls with harness scores |
| `/api/v1/webhooks/call-completed` | POST | Receive webhooks from voice AI platforms |
| `/api/v1/harness/status` | GET | Validation harness state |

See [BACKEND.md](BACKEND.md) for the full 33-endpoint API reference.

## Deploy

```bash
# Docker
docker build -t voicescope . && docker run -p 8000:8000 --env-file .env voicescope

# Docker Compose
docker compose up -d

# Railway
# ![Deploy](https://railway.app/button.svg)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
