# VoiceScope

Open source observability API for voice AI agents.

Upload a call recording → get a structured JSON report covering intent, sentiment, hallucination detection, outcome, and escalation signal.

## Architecture

```
Audio File
    │
    ▼
┌─────────────────────┐
│  Transcription Agent │  ← OpenAI Whisper
│  (audio → text)      │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Analysis Agent     │  ← GPT-4o + RAG (ChromaDB)
│  intent / sentiment  │
│  hallucination       │
│  outcome / escalation│
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    Report Agent      │  ← GPT-4o structured output
│  quality score       │
│  findings + recs     │
└─────────────────────┘
    │
    ▼
Structured JSON Report
```

Each agent shares a `PipelineContext` object. Each stage enriches it. The report agent assembles the final output and stores the transcript in ChromaDB for future RAG retrieval.

## Quick Start

```bash
git clone https://github.com/ShivamChavan01/voicescope
cd voicescope

cp .env.example .env
# Add your OPENAI_API_KEY to .env

pip install -r requirements.txt
uvicorn main:app --reload
```

## Usage

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@call_recording.mp3"
```

## Sample Response

```json
{
  "run_id": "abc-123",
  "generated_at": "2026-06-01T06:00:00",
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
  }
}
```

## Deploy on Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

1. Push to GitHub
2. Connect repo on Railway
3. Add `OPENAI_API_KEY` env var
4. Deploy

## Tech Stack

- **FastAPI** — API layer
- **OpenAI Whisper** — transcription
- **GPT-4o** — analysis + report generation
- **ChromaDB** — RAG storage for past calls
- **Pydantic** — structured outputs
- **Docker** — containerized deployment

## License

MIT
