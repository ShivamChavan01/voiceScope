# VoiceScope

[![CI](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Voice AI agents hallucinate. Nobody catches it. VoiceScope does.**

Analyze any voice AI call recording and get: intent, sentiment, hallucination detection, policy violations, quality score, and cost — in one command. A 7-layer validation harness catches LLM errors before they reach your dashboard.

## 30-Second Demo

```bash
# Install
pip install voicescope

# Set one API key (Groq free tier works)
export GROQ_API_KEY=gsk_your_key_here

# Analyze a call
voicescope analyze call.mp3
```

Output:
```
  Truth Score: 0.92  [PASS]  Confidence: high

  Transcript:
  Agent: How can I help you today? Customer: I want to cancel my subscription...

  Intent:      cancel subscription
  Sentiment:   negative
  Outcome:     resolved
```

## Quick Start (Full)

```bash
git clone https://github.com/ShivamChavan01/voicescope && cd voicescope
pip install -e .
voicescope init          # interactive setup
voicescope serve         # start API server at localhost:8000
```

Or with Docker:
```bash
docker compose up -d
```

## What It Does

```
Audio File ──→ Transcription ──→ Analysis ──→ Report ──→ Validation
                (Deepgram)      (LLM+RAG)    (LLM)      (7 layers)
                                    │
                              Knowledge Base
                              (your policies)
```

**The pipeline:**
1. **Transcribe** — Deepgram Nova-2, Gemini, or Whisper with speaker diarization
2. **Classify speakers** — LLM identifies agent vs customer
3. **Analyze** — Intent, sentiment, hallucination detection, outcome, escalation
4. **Ground in your policies** — RAG against your knowledge base (refund rules, compliance, etc.)
5. **Generate report** — Quality score, findings, recommendations
6. **Validate** — 7-layer harness catches LLM errors (wrong types, ungrounded claims, contradictions)

## Validation Harness

Every LLM output passes 7 deterministic checks before reaching your dashboard:

| # | Layer | Catches | Weight |
|---|-------|---------|--------|
| 1 | Schema | Wrong types, bad enums, missing fields | 0.30 |
| 2 | Citations | Findings not in the transcript | 0.15 |
| 3 | Facts | Numbers/dates contradict transcript | 0.15 |
| 4 | Sentiment | "Angry" transcript labeled "positive" | 0.10 |
| 5 | Outcome | "Resolved" with no resolution evidence | 0.10 |
| 6 | Escalation | "Escalated" with no manager mention | 0.05 |
| 7 | Duplicate | Same analysis repeated within 5 min | 0.05 |

**Truth Score** = weighted average (0.0–1.0). Every response includes `harness.truth_score`.

## CLI Commands

```bash
voicescope analyze <file>       # Analyze a call recording
voicescope analyze <file> --json # Output raw JSON
voicescope serve                 # Start API server
voicescope init                  # Interactive setup
voicescope status                # Check dependencies & config
```

## Configuration

```bash
# .env (run voicescope init for interactive setup)
LLM_PROVIDER=groq               # openai, anthropic, gemini, groq, ollama, mistral
GROQ_API_KEY=gsk_...            # Free tier: llama-3.3-70b-versatile
DEEPGRAM_API_KEY=...            # Nova-2 with diarization ($200 free credits)
VALID_API_KEYS=your-key         # Required — server returns 503 if not set
```

| Provider | Default Model | Cost |
|----------|---------------|------|
| Groq | `llama-3.3-70b-versatile` | Free tier |
| OpenAI | `gpt-4o` | $2.50/$10.00 per 1M tokens |
| Anthropic | `claude-sonnet-4` | $3.00/$15.00 per 1M tokens |
| Gemini | `gemini-1.5-pro` | $1.25/$5.00 per 1M tokens |
| Ollama | `llama3.1` | Free (local) |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analyze` | POST | Upload audio → full analysis |
| `/api/v1/analyze/stream` | POST | SSE streaming with progress |
| `/api/v1/runs` | GET | List analyzed calls |
| `/api/v1/webhooks/call-completed` | POST | Auto-detect 7 voice AI platforms |
| `/api/v1/harness/status` | GET | Validation harness state |

See [BACKEND.md](BACKEND.md) for the full 33-endpoint reference.

## Features

- **Multi-Provider LLM** — OpenAI, Anthropic, Gemini, Groq, Ollama, Mistral
- **3-Stage Pipeline** — Transcription → Analysis → Report with speaker classification
- **Knowledge Base Grounding** — RAG against your policies for hallucination detection
- **Monitoring & Alerting** — Threshold-based alerts on hallucination rate, quality score
- **QA Cohorts** — Weighted scoring, resolution criteria, pass/fail tracking
- **Custom Extractions** — User-defined post-call analysis schemas
- **Content Guardrails** — Harmful content detection + PII redaction
- **Streaming SSE** — Real-time pipeline progress
- **Batch Processing** — Analyze multiple files with webhook callbacks
- **Cost Tracking** — Token usage and cost per call across providers
- **PostgreSQL + SQLite** — Production DB with local fallback

## Architecture

```
voicescope/
├── agents/              # Transcription, Speaker, Analysis, Report agents
├── api/                 # FastAPI routes, SSE streaming, webhook handlers
├── core/                # Pipeline, harness, knowledge base, batch processing
├── llm_providers/       # OpenAI, Anthropic, Gemini, Groq, Ollama, Mistral
├── stt_providers/       # Deepgram, Whisper, Gemini STT
├── storage/             # PostgreSQL/SQLite stores, ChromaDB vector store
├── middleware/          # Auth, rate limiting
├── tests/               # 267 tests (unit, integration, e2e)
├── cli.py               # CLI entry point
└── main.py              # FastAPI app
```

## Deploy

```bash
# Docker
docker build -t voicescope . && docker run -p 8000:8000 --env-file .env voicescope

# Docker Compose (with PostgreSQL)
docker compose up -d

# Railway
# ![Deploy](https://railway.app/button.svg)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
