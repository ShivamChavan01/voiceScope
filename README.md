# VoiceScope

[![CI](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivamChavan01/voicescope/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-267-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Voice AI agents hallucinate. They promise refunds that don't exist, cite policies that aren't real, and escalate when they shouldn't. Nobody catches it. VoiceScope does.

VoiceScope analyzes voice AI call recordings and catches hallucinations, policy violations, and quality issues — before your customers notice. It's a 3-agent pipeline with a 7-layer validation harness that catches LLM errors deterministically, not with another LLM call.

## Try It (30 seconds)

```bash
pip install voicescope
export GROQ_API_KEY=gsk_your_key_here    # free tier works
voicescope analyze call.mp3
```

You get:

```
  ┌─────────────────────────────────────────────────────┐
  │  Truth Score: 0.92  [PASS]  Confidence: high        │
  ├─────────────────────────────────────────────────────┤
  │                                                     │
  │  Transcript:                                        │
  │  Agent: How can I help you today?                   │
  │  Customer: I want to cancel my subscription...      │
  │                                                     │
  │  Intent:      cancel subscription                   │
  │  Sentiment:   negative                              │
  │  Outcome:     resolved                              │
  │  Hallucination: clean                               │
  │                                                     │
  │  Harness Layers:                                    │
  │    schema          ████████████████████ 0.95        │
  │    citations       ████████████████░░░░ 0.80        │
  │    facts           ████████████████████ 0.90        │
  │    sentiment       ████████████████████ 1.00        │
  │    outcome         ██████████████████░░ 0.85        │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

## How It Works

```
                          Knowledge Base
                          (your policies)
                               │
Audio ──→ Transcribe ──→ Analyze ──→ Report ──→ Validate
          (Deepgram)    (LLM+RAG)    (LLM)     (7 rules)
               │
          Speaker ID
          (agent vs customer)
```

1. **Transcribe** — Deepgram Nova-2 with speaker diarization (or Gemini/Whisper)
2. **Classify speakers** — LLM identifies who's the agent, who's the customer
3. **Analyze** — Intent, sentiment, hallucination detection, outcome, escalation
4. **Ground in your policies** — RAG against your knowledge base. "Did the agent violate *your* refund policy?" not just "did the agent lie?"
5. **Generate report** — Quality score, findings, recommendations
6. **Validate** — 7-layer harness catches LLM errors before they reach your dashboard

## The Harness (This Is the Hard Part)

Anyone can call an LLM and get a JSON response. The hard part is knowing when the LLM is wrong. VoiceScope's validation harness runs 7 deterministic checks on every output:

| # | Layer | What It Catches | Weight |
|---|-------|-----------------|--------|
| 1 | **Schema** | Wrong types, bad enums, missing fields | 0.30 |
| 2 | **Citations** | Findings not grounded in the transcript | 0.15 |
| 3 | **Facts** | Numbers, dates, promises that contradict the transcript | 0.15 |
| 4 | **Sentiment** | "Angry" transcript labeled "positive" | 0.10 |
| 5 | **Outcome** | "Resolved" with no resolution evidence | 0.10 |
| 6 | **Escalation** | "Escalated" with no manager mention | 0.05 |
| 7 | **Duplicate** | Same analysis repeated within 5 minutes | 0.05 |

Every API response includes a `harness` field with `truth_score` (0.0–1.0), `confidence`, `layer_scores`, and `validation_errors`. No black boxes.

## Get Running

### Option A: CLI (fastest)

```bash
git clone https://github.com/ShivamChavan01/voicescope && cd voicescope
pip install -e .
voicescope init              # pick your provider, set keys
voicescope analyze call.mp3  # see results
voicescope serve             # start API server
```

### Option B: Docker

```bash
docker compose up -d
# API at localhost:8000, docs at localhost:8000/docs
```

### Option C: API only

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Configuration

```bash
# .env
LLM_PROVIDER=groq               # openai | anthropic | gemini | groq | ollama | mistral
GROQ_API_KEY=gsk_...            # free tier: llama-3.3-70b-versatile
DEEPGRAM_API_KEY=...            # nova-2 with diarization ($200 free credits)
VALID_API_KEYS=your-key-here    # required — server returns 503 without it
```

| Provider | Model | Cost |
|----------|-------|------|
| Groq | `llama-3.3-70b-versatile` | Free |
| OpenAI | `gpt-4o` | $2.50/$10 per 1M tokens |
| Anthropic | `claude-sonnet-4` | $3/$15 per 1M tokens |
| Gemini | `gemini-1.5-pro` | $1.25/$5 per 1M tokens |
| Ollama | `llama3.1` | Free (local) |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/v1/analyze` | Upload audio, get full analysis |
| `POST /api/v1/analyze/stream` | SSE streaming with progress events |
| `GET /api/v1/runs` | List analyzed calls with harness scores |
| `POST /api/v1/webhooks/call-completed` | Auto-detects Vapi, Retell, Bland, Bolna, Synthflow, Air.ai |
| `GET /api/v1/harness/status` | Validation harness state |

Full 33-endpoint reference in [BACKEND.md](BACKEND.md).

## Built With

- **FastAPI** + **uvicorn** — async API server
- **Deepgram** / **Gemini** / **Whisper** — speech-to-text with diarization
- **6 LLM providers** — OpenAI, Anthropic, Gemini, Groq, Ollama, Mistral
- **ChromaDB** — vector store for RAG context from past calls
- **PostgreSQL** (Supabase) + **SQLite** fallback — production + local
- **Pydantic** — schema validation, structured outputs
- **asyncpg** — async PostgreSQL connection pool with lock

## Engineering

This isn't a notebook demo. It's built like production software:

- **267 tests** — unit, integration, and end-to-end
- **Security audit** — SQL injection fixed (4 locations), SSRF blocked, auth middleware, rate limiting
- **Connection pooling** — `asyncio.Lock` around pool creation, stale cache removed
- **Error isolation** — DB logging failures don't kill API responses
- **Parameterized queries** — `$1 || ' minutes'::interval` for PostgreSQL, `?` for SQLite
- **Streaming** — SSE with `fetch()` + `ReadableStream`, not EventSource
- **LLM timeouts** — 60s on OpenAI, Anthropic clients
- **Bounds checking** — `response.choices[0]` validated before access

```
voicescope/
├── agents/          Transcription, Speaker, Analysis, Report
├── api/             Routes, SSE streaming, webhook handlers
├── core/            Pipeline, harness, knowledge base, batch
├── llm_providers/   6 providers with strategy pattern
├── stt_providers/   3 STT providers with registry
├── storage/         PostgreSQL/SQLite stores, ChromaDB
├── middleware/       Auth, rate limiting
├── tests/           276 tests
├── cli.py           CLI entry point
└── main.py          FastAPI app
```

## Deploy

```bash
# Docker
docker build -t voicescope . && docker run -p 8000:8000 --env-file .env voicescope

# Docker Compose (with PostgreSQL)
docker compose up -d
```

## License

MIT
