# VoiceScope Backend — Complete Architecture Reference

## Overview

VoiceScope is an open-source voice AI observability platform built with FastAPI. It analyzes voice AI calls through a 3-stage pipeline (transcription → analysis → report) with a 7-layer validation harness that detects hallucinations, verifies facts, and tracks quality.

**Stack:** Python 3.12, FastAPI, SQLite, ChromaDB, OpenAI Whisper, 5 LLM providers

---

## Directory Structure

```
voicescope/
├── main.py                          # FastAPI app entrypoint
├── api/
│   ├── routes.py                    # All HTTP route handlers (605 lines)
│   ├── schemas.py                   # Pydantic models + webhook parsers (489 lines)
│   └── sse.py                       # Server-Sent Events streaming
├── core/
│   ├── pipeline.py                  # 3-stage pipeline orchestrator
│   ├── context.py                   # Shared PipelineContext dataclass
│   ├── harness.py                   # 7-layer validation harness (302 lines)
│   ├── citations.py                 # Layer 2: Citation verification
│   ├── facts.py                     # Layer 3: Fact extraction & verification
│   ├── sentiment_check.py           # Layer 4: Sentiment consistency check
│   ├── outcome_check.py             # Layers 5-6: Outcome evidence + escalation
│   ├── audio_quality.py             # Audio quality pre-check (runs but not scored)
│   ├── calibration.py               # Confidence calibration (long-term project)
│   ├── optimizer.py                 # Auto-tune harness layer weights
│   ├── benchmark.py                 # Run labeled test data through harness
│   ├── self_improve.py              # Self-improvement loop orchestrator
│   ├── prompt_tracker.py            # Track prompt performance
│   ├── feedback.py                  # User feedback submission
│   ├── knowledge_base.py            # ChromaDB-backed policy KB for RAG
│   ├── batch.py                     # Async batch processor
│   ├── assertions.py                # Assertion engine for test harness
│   ├── test_harness.py              # Test harness runner
│   ├── qa.py                        # QA cohort system
│   └── extractions.py               # Custom extraction schema system
├── agents/
│   ├── transcription_agent.py       # Agent 1: Audio → Text (Deepgram/Gemini/Whisper)
│   ├── analysis_agent.py            # Agent 2: LLM-powered analysis
│   ├── report_agent.py              # Agent 3: Report generation + ChromaDB store
│   └── speaker_agent.py             # Agent 4: Speaker classification (Agent/Customer)
├── storage/
│   ├── chroma_store.py              # ChromaDB vector store (RAG)
│   ├── cost_store.py                # SQLite cost tracking
│   └── monitoring.py                # SQLite metrics, alerts, incidents (305 lines)
├── llm_providers/
│   ├── base.py                      # Abstract LLMProvider + CompletionResult
│   ├── registry.py                  # Provider registry + circuit breakers
│   ├── openai_provider.py           # OpenAI (gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo)
│   ├── anthropic_provider.py        # Anthropic (claude-sonnet-4, claude-3.5-sonnet, haiku)
│   ├── gemini_provider.py           # Gemini (1.5-pro, 1.5-flash, 2.0-flash)
│   ├── mistral_provider.py          # Mistral (large, medium, small, mixtral-8x7b)
│   └── ollama_provider.py           # Ollama local (llama3.1)
├── middleware/
│   ├── auth.py                      # API key authentication
│   └── rate_limit.py                # Per-IP rate limiting (60 RPM)
├── utils/
│   ├── logger.py                    # Loguru structured logging
│   ├── tracing.py                   # Request context + stage timing
│   ├── security.py                  # SSRF protection, key hashing, path validation
│   ├── guardrails.py                # Content guardrails, PII redaction
│   ├── resilience.py                # Circuit breaker + retry decorator
│   └── exceptions.py                # Custom exceptions (deprecated — kept for compat)
├── sdk/
│   └── voicescope/
│       ├── client.py                # Python SDK client (async + sync)
│       └── models.py                # SDK Pydantic models
├── knowledge/
│   └── business_policy.md           # Sample e-commerce support policy
├── tests/                           # 194 tests, 15 test files
├── Dockerfile                       # Multi-stage build
├── docker-compose.yml
├── railway.toml                     # Railway deployment
├── pyproject.toml                   # Package config
├── .github/workflows/ci.yml         # CI/CD pipeline
└── PLAN-frontend.md                 # Frontend implementation plan
```

---

## Pipeline Architecture

### Data Flow

```
Audio Input (file or webhook)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Middleware Pipeline                                 │
│  1. request_context_middleware → correlation_id      │
│  2. RateLimitMiddleware → 60 RPM per IP             │
│  3. APIKeyAuthMiddleware → X-API-Key validation      │
│  4. CORSMiddleware → CORS_ORIGINS                    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Layer 11: Audio Quality Pre-Check                   │
│  - Size > 1KB                                       │
│  - Duration 1s-3600s                                │
│  - Format: mp3/wav/m4a/ogg/flac/webm/mp4            │
│  - Silence detection (>95% zeros)                   │
│  → should_proceed: bool                             │
└─────────────────────────────────────────────────────┘
    │ (if should_proceed)
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1: TranscriptionAgent                        │
│  - OpenAI Whisper API (whisper-1, verbose_json)     │
│  - Writes temp file → API → cleanup                 │
│  → ctx.raw_transcript                               │
│  → ctx.language_detected                            │
│  → ctx.audio_duration_seconds                       │
└─────────────────────────────────────────────────────┘
    │ (if transcription succeeded)
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage 2: AnalysisAgent                             │
│  - Word count check                                 │
│  - If >4000 words: hierarchical summarization       │
│    (split by speaker turns → chunk to 1000 words)   │
│  - RAG: query ChromaDB for 3 similar transcripts    │
│  - Claims extraction via LLM                        │
│  - KB context: query KnowledgeBase for each claim   │
│  - Main analysis prompt                             │
│  → ctx.intent                                       │
│  → ctx.sentiment_arc                                │
│  → ctx.hallucination_detected                       │
│  → ctx.hallucination_evidence                       │
│  → ctx.outcome                                      │
│  → ctx.escalation_signal                            │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage 3: ReportAgent                               │
│  - LLM generates: executive summary, quality_score, │
│    key_findings, recommendations                    │
│  - Stores transcript in ChromaDB for future RAG     │
│  → ctx.report (final output)                        │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: ReportAgent                                       │
│  - LLM generates: executive summary, quality_score,        │
│    key_findings, recommendations                            │
│  - Stores transcript in ChromaDB for future RAG             │
│  → ctx.report (final output)                                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  SpeakerAgent (optional)                                    │
│  - Classifies Agent vs Customer                             │
│  → ctx.transcript_speakers                                  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Post-Processing                                     │
│  - _log_cost() → CostStore (SQLite)                 │
│  - _log_metrics() → MonitoringStore (SQLite)        │
└─────────────────────────────────────────────────────┘
    │
    ▼
  Response (AnalyzeResponse)
```

---

## 7-Layer Validation Harness

| Layer | Module | What It Does | Score Weight |
|-------|--------|-------------|--------------|
| 1 | `harness.py` | Schema validation — Pydantic model check, enum values, field types | 0.30 |
| 2 | `citations.py` | Citation verification — fuzzy match findings against transcript (0.6 threshold) | 0.15 |
| 3 | `facts.py` | Fact extraction — pulls numbers, dates, promises, actions; verifies against analysis | 0.15 |
| 4 | `sentiment_check.py` | Sentiment consistency — word-list cue matching (35 neg, 25 pos, 15 neutral) | 0.10 |
| 5 | `outcome_check.py` | Outcome evidence — checks if resolved/unresolved/escalated has transcript markers | 0.10 |
| 6 | `outcome_check.py` | Escalation verification — checks if escalation_signal=True has evidence | 0.05 |
| 7 | `harness.py` | Duplicate detection — MD5 hash with 5-minute window | 0.05 |

**Truth Score** = weighted average: schema(0.30) + citations(0.15) + facts(0.15) + sentiment(0.10) + outcome(0.10) + escalation(0.05) + duplicate(0.05)

*Additional metrics tracked but not scored: response time, token usage, audio quality, confidence calibration.*

---

## 33 API Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root info |
| GET | `/api/v1/health` | Service health check |

### Core Analysis
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/analyze` | Upload audio → full pipeline analysis |
| POST | `/api/v1/analyze/stream` | SSE streaming analysis |

### Batch Processing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/batch` | Upload up to 20 files, get batch_id |
| GET | `/api/v1/batch/{batch_id}` | Batch processing status |
| GET | `/api/v1/batch/{batch_id}/results` | Batch results (when complete) |

### Cost Tracking
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/costs` | LLM cost summary by provider/model |

### Webhook Integration
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhooks/call-completed` | Receive webhook from voice platforms |

### Monitoring & Alerting
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/monitoring/metrics` | Metrics summary (hallucination rate, quality, cost) |
| GET | `/api/v1/monitoring/alerts` | List alert rules |
| POST | `/api/v1/monitoring/alerts` | Create threshold-based alert rule |
| DELETE | `/api/v1/monitoring/alerts/{rule_id}` | Delete alert rule |
| GET | `/api/v1/monitoring/incidents` | List triggered incidents |
| POST | `/api/v1/monitoring/check` | Manually trigger alert evaluation |

### QA System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/qa/cohorts` | List QA cohorts |
| POST | `/api/v1/qa/cohorts` | Create QA cohort |
| POST | `/api/v1/qa/cohorts/{cohort_id}/score` | Score a call |
| GET | `/api/v1/qa/cohorts/{cohort_id}/results` | Get scoring results |

### Custom Extractions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/extractions/schemas` | List extraction schemas |
| POST | `/api/v1/extractions/schemas` | Create schema (text/boolean/number/category) |
| DELETE | `/api/v1/extractions/schemas/{schema_id}` | Delete schema |
| POST | `/api/v1/extractions/schemas/{schema_id}/run` | Run extractions on transcript |
| GET | `/api/v1/extractions/schemas/{schema_id}/results` | Get extraction results |

### Guardrails
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/guardrails/status` | Guardrail status |
| POST | `/api/v1/guardrails/check` | Check text for harmful content / PII |

### Validation Harness
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/harness/status` | Harness summary |
| POST | `/api/v1/harness/run` | Run all test cases |
| POST | `/api/v1/harness/feedback` | Submit feedback for a run |
| GET | `/api/v1/harness/calibration` | Calibration metrics |
| POST | `/api/v1/harness/validate` | Validate arbitrary text |

### Self-Improvement Loop
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/loop/status` | Loop status |
| POST | `/api/v1/loop/run` | Run benchmark → optimize → track → suggest |
| GET | `/api/v1/loop/benchmark` | Run benchmark, get accuracy per layer |
| GET | `/api/v1/loop/suggestions` | Prompt improvement suggestions |
| GET | `/api/v1/loop/weights` | Current harness layer weights |

---

## Agent Architecture

### Pipeline Agents (run in sequence)

#### 1. TranscriptionAgent (`agents/transcription_agent.py`)
- **Input:** audio bytes, filename
- **LLM:** OpenAI Whisper API (`whisper-1`)
- **Output:** raw_transcript, language_detected, audio_duration_seconds
- **Temp file:** writes audio to temp, sends to API, cleans up

#### 2. AnalysisAgent (`agents/analysis_agent.py`)
- **Input:** PipelineContext with raw_transcript
- **LLM:** Configurable via `LLM_PROVIDER` env var
- **RAG:** Queries ChromaDB for 3 similar past transcripts
- **KB:** Queries KnowledgeBase for policy violations per claim
- **Hierarchical summarization:** transcripts >4000 words split by speaker turns into 1000-word chunks
- **Output:** intent, sentiment_arc, hallucination_detected, hallucination_evidence, outcome, escalation_signal

#### 3. ReportAgent (`agents/report_agent.py`)
- **Input:** Full PipelineContext
- **LLM:** Configurable
- **Output:** executive_summary, quality_score, key_findings, recommendations
- **Side effect:** Stores transcript in ChromaDB for future RAG

### Optional Agents

#### 4. SpeakerAgent (`agents/speaker_agent.py`)
- Classifies speakers as Agent or Customer using LLM
- Extracts speaker roles and talk-time ratio

---

## LLM Providers

| Provider | Class | Default Model | API Key Env Var |
|----------|-------|---------------|-----------------|
| OpenAI | `OpenAIProvider` | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `AnthropicProvider` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| Gemini | `GeminiProvider` | `gemini-1.5-pro` | `GOOGLE_API_KEY` |
| Groq | `GroqProvider` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Mistral | `MistralProvider` | `mistral-large-latest` | `MISTRAL_API_KEY` |
| Ollama | `OllamaProvider` | `llama3.1` | `OLLAMA_BASE_URL` |

### Pricing (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| claude-sonnet-4 | $3.00 | $15.00 |
| claude-3.5-haiku | $0.80 | $4.00 |
| gemini-1.5-pro | $1.25 | $5.00 |
| gemini-1.5-flash | $0.075 | $0.30 |
| llama-3.3-70b (Groq) | $0.59 | $0.79 |
| mistral-large | $2.00 | $6.00 |
| Ollama (local) | Free | Free |

### Provider Selection
- Set `LLM_PROVIDER` env var (default: `openai`)
- Each provider has a `CircuitBreaker` instance
- Auto-registration at import time (graceful fallback if SDK not installed)

---

## Storage Modules

| Store | Backend | DB File | What It Stores |
|-------|---------|---------|----------------|
| `ChromaStore` | ChromaDB | `./chroma_db/` | Vector embeddings of transcripts (RAG). Collection: `voice_calls` |
| `CostStore` | SQLite | `./costs.db` | Per-run LLM cost logs: provider, model, tokens, cost_usd |
| `MonitoringStore` | SQLite | `./monitoring.db` | Call metrics, alert rules, triggered incidents |
| `KnowledgeBase` | ChromaDB | `./chroma_db/` | Policy document chunks. Collection: `policy_kb` |
| `QAStore` | SQLite | `./qa.db` | QA cohorts, scoring results |
| `ExtractionStore` | SQLite | `./extractions.db` | Custom extraction schemas and results |
| `PromptTracker` | JSON | `./prompt_tracker.json` | Prompt version records, accuracy, failure patterns |
| `CalibrationOptimizer` | JSON | `./optimizer.json` | Layer weight history, optimization results |
| `ConfidenceCalibrator` | JSON | `./calibration.json` | Calibration entries |

---

## Middleware Stack

Applied in reverse order of addition:

1. **`request_context_middleware`** — Generates correlation_id, run_id, sets ContextVar. Adds security headers (nosniff, DENY, strict-origin).

2. **`RateLimitMiddleware`** — Per-IP sliding window. Default 60 RPM. Tracks up to 10,000 IPs with cleanup every 300s.

3. **`APIKeyAuthMiddleware`** — Validates `X-API-Key` against `VALID_API_KEYS`. Exempt: `/health`, `/docs`, `/redoc`, `/openapi.json`, `/`, `/api/v1/health`. Returns 503 if no keys configured.

4. **`CORSMiddleware`** — Allows GET/POST. Headers: `X-API-Key`, `Content-Type`, `X-Correlation-ID`.

---

## WebSocket / SSE

### SSE Endpoint
**`POST /api/v1/analyze/stream`** — Returns `text/event-stream`

Events:
```json
{"event": "started", "run_id": "..."}
{"event": "stage_complete", "stage": "transcription", "run_id": "..."}
{"event": "stage_complete", "stage": "analysis", "run_id": "..."}
{"event": "stage_complete", "stage": "report", "run_id": "..."}
{"event": "complete", "result": {...}}
```

### WebSocket Endpoints
None.

---

## Webhook Platform Support

| Platform | Detection | Parser |
|----------|-----------|--------|
| Vapi | `message.type` in end-of-call-report | `parse_vapi_webhook()` |
| Retell | `event` in call_ended/call_analyzed | `parse_retell_webhook()` |
| Bland.ai | `concatenated_transcript` or `transcripts[]` | `parse_bland_webhook()` |
| Bolna | `telephony_data` dict present | `parse_bolna_webhook()` |
| Synthflow | `collected_variables` or `executed_actions` | `parse_synthflow_webhook()` |
| Air.ai | `call` dict with `sid` + `callRecordingUrl` | `parse_airai_webhook()` |
| Generic | Fallback — recursive field discovery | `parse_generic_webhook()` |

All parsers normalize to `WebhookEvent` model.

---

## Pydantic Models

### API Models

| Model | Fields |
|-------|--------|
| `AnalyzeResponse` | run_id, generated_at, pipeline, transcript_meta, analysis, report |
| `ErrorResponse` | run_id, status, errors |
| `HealthResponse` | status, service, version |
| `WebhookEvent` | platform, event_type, call_id, recording_url, transcript, duration_ms, ended_reason, metadata, raw |
| `AlertRuleRequest` | name, metric, comparator, threshold, window_minutes, notify_url, notify_email |
| `QACohortRequest` | name, agent_filter, platform_filter, min/max_duration, sampling_pct, weekly_max, criteria |
| `QAScoreRequest` | run_id, metrics |
| `ExtractionSchemaRequest` | name, description, fields |
| `ExtractionRunRequest` | run_id, transcript, metadata |
| `GuardrailCheckRequest` | text, check_type |
| `FeedbackRequest` | run_id, feedback, notes |

### Core Models

| Model | Fields |
|-------|--------|
| `PipelineContext` | run_id, created_at, raw_transcript, audio_duration, language, intent, sentiment_arc, hallucination_*, outcome, escalation_signal, word_count, chunk_count, report, provider_*, tokens, cost_usd, errors, stages_completed |
| `AnalysisOutput` | intent, sentiment_arc, hallucination_detected, hallucination_evidence, outcome, escalation_signal, findings |
| `ReportOutput` | quality_score, key_findings, recommendations, summary |
| `ValidationResult` | passed, confidence, errors, warnings, layer_scores |
| `HarnessResult` | truth_score, confidence, validation_passed, validation_errors, layer_scores, raw_output, validated_output, response_time_ms, token_usage, duplicate_hash, audio_quality_score |
| `CitationResult` | coverage, matched, unmatched, total_findings |
| `CrossCheckResult` | agreement_rate, disagreements, checked |
| `Fact` | text, fact_type, value |
| `FactVerificationResult` | accuracy, facts_found, contradictions |
| `SentimentCheckResult` | consistent, consistency_score, suggested_sentiment, cues_found |
| `OutcomeCheckResult` | has_evidence, evidence_score, evidence_found, missing_evidence |
| `AudioQualityResult` | quality_score, issues, should_proceed |
| `CalibrationEntry` | timestamp, truth_score, confidence, user_feedback, run_id |
| `CalibrationResult` | total_predictions, high/medium/low_confidence_accuracy, calibration_error, feedback_count |
| `LayerPerformance` | name, accuracy, weight, samples, false_positives, false_negatives |
| `OptimizationResult` | old_weights, new_weights, improvement, changes_made |
| `PromptRecord` | prompt_name, version, accuracy, total_runs, failure_patterns, created_at |
| `FailurePattern` | pattern, count, last_seen, suggestion |
| `LoopResult` | timestamp, benchmark, optimization, suggestions, prompt_stats, status |
| `BenchmarkResult` | test_id, name, truth_score, layer_scores, sentiment/outcome/hallucination/escalation_correct, citation_coverage, fact_accuracy, contradictions, errors |
| `BenchmarkSummary` | total_tests, avg_truth_score, accuracy per type, weakest/strongest_layer, results |
| `FeedbackEntry` | run_id, feedback, notes |
| `ExtractionField` | name, description, field_type, options, prompt |
| `ExtractionSchema` | name, description, fields |
| `ResolutionCriterion` | name, description, weight, metric_type |
| `QACohort` | name, agent_filter, platform_filter, min/max_duration, sampling_pct, weekly_max, criteria |

### LLM Provider Models

| Model | Fields |
|-------|--------|
| `CompletionResult` | content, model, provider, input_tokens, output_tokens, cost_usd |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `openai` | Active LLM provider |
| `OPENAI_API_KEY` | — | OpenAI API key (also used for Whisper) |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google Gemini API key |
| `MISTRAL_API_KEY` | — | Mistral API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `VALID_API_KEYS` | — | Comma-separated valid API keys |
| `RATE_LIMIT_RPM` | `60` | Requests per minute per IP |
| `APP_ENV` | — | Set to `production` to disable docs |
| `CORS_ORIGINS` | — | Comma-separated allowed origins |
| `CROSS_CHECK_ENABLED` | `false` | Enable Layer 3 cross-check |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `COST_DB_PATH` | `./costs.db` | Cost tracking DB |
| `MONITORING_DB_PATH` | `./monitoring.db` | Monitoring DB |
| `QA_DB_PATH` | `./qa.db` | QA system DB |
| `EXTRACTIONS_DB_PATH` | `./extractions.db` | Extractions DB |
| `CALIBRATION_DB_PATH` | `./calibration.json` | Calibration data |
| `OPTIMIZER_DB_PATH` | `./optimizer.json` | Optimizer data |
| `PROMPT_TRACKER_DB_PATH` | `./prompt_tracker.json` | Prompt tracking data |

---

## Utilities

| Module | What It Provides |
|--------|-----------------|
| `utils/logger.py` | Loguru structured logging with correlation IDs. Console (INFO) + daily rotating file (DEBUG, JSON, 7-day retention). |
| `utils/tracing.py` | `RequestContext` (run_id, correlation_id, stage_timings) in ContextVar. Stage timing (start/end/duration_ms). |
| `utils/security.py` | SSRF protection (HTTPS-only, private IP block with DNS resolution). API key hashing (SHA-256). Log input sanitization. |
| `utils/guardrails.py` | Content guardrails: harmful content detection (self-harm, violence, harassment, medical/financial advice). PII redaction (email, phone, SSN, credit card, IP). |
| `utils/resilience.py` | `CircuitBreaker` (closed → open → half-open). `@with_retry` decorator (exponential backoff). |
| `utils/exceptions.py` | `VoiceScopeError` → `TranscriptionError`, `AnalysisError`, `ReportError`, `ProviderError` → `RateLimitError`, `CircuitBreakerOpenError`. |

---

## Tests

194 tests across 15 files:

| Test File | What It Tests |
|-----------|---------------|
| `test_api.py` | API endpoint tests |
| `test_assertions.py` | AssertionEngine unit tests |
| `test_context.py` | PipelineContext tests |
| `test_cost_store.py` | CostStore SQLite tests |
| `test_exceptions.py` | Exception hierarchy tests |
| `test_harness.py` | 51 tests for 13 harness layers |
| `test_new_features.py` | Monitoring, QA, extractions, guardrails (with setup_method for table cleanup) |
| `test_providers.py` | Provider registry tests |
| `test_resilience.py` | Circuit breaker + retry tests |
| `test_self_improve.py` | 21 tests for benchmark/optimizer/tracker/loop |
| `test_webhooks.py` | Webhook integration tests |
| `test_webhook_parsers.py` | Parser unit tests |
| `test_cases.json` | Sample harness test cases |
| `test_data_labeled.json` | 10 labeled transcripts with ground truth |
| `conftest.py` | Shared test fixtures |

Run: `pytest tests/ -v`

---

## Deployment

### Docker
- Multi-stage build, non-root user
- `${PORT:-8000}` fallback for Railway
- Health check: `/api/v1/health`

### Railway
- `railway.toml` config
- Docker build, healthcheck
- Env vars: `LLM_PROVIDER=gemini`, `GOOGLE_API_KEY`, `VALID_API_KEYS`, `APP_ENV=production`

### CI/CD (GitHub Actions)
- 4 parallel jobs: lint (ruff), typecheck (mypy), test (pytest), audit (pip-audit)
- Docker build depends on all 4
- `sdk/` excluded from mypy
- ChromaDB CVE-2026-45829 ignored in pip-audit

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Provider Registry pattern | Single env var `LLM_PROVIDER` switches entire pipeline |
| Circuit breaker per provider | Prevents cascade failures when one provider is down |
| Persistent `self._conn` in stores | Supports `:memory:` in tests, avoids per-call connection overhead |
| Singleton stores via `@lru_cache` | Simple, no asyncio.Lock needed |
| Hierarchical summarization | Handles 30+ min transcripts without token limits |
| ChromaDB for RAG | Lightweight, no external service needed |
| SQLite for all stores | Simple deployment, no Postgres/MySQL dependency |
| Regex-based guardrails | Zero-latency blocking (not LLM-based) |
| `BaseHTTPMiddleware` limitation | Must return `JSONResponse`, not raise `HTTPException` |
| `sdk/` excluded from mypy | SDK has different type expectations |
| No WebSocket endpoints | SSE is simpler for streaming analysis results |
| Webhook auto-detection | Universal generic parser handles unknown platforms |
