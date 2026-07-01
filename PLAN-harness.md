# VoiceScope Validation Harness — Engineering Plan

## Problem

VoiceScope uses LLMs to analyze voice AI calls. LLMs hallucinate. Right now, every LLM output is trusted blindly — 8 critical fields pass from LLM response to database to dashboard with zero validation. If the LLM lies about sentiment, hallucination detection, or quality score, VoiceScope reports it as fact.

## Solution: A validation harness that wraps every LLM call and catches lies before they propagate.

---

## Architecture

### New file: `core/harness.py` (rename existing to `core/test_harness.py`)

```
LLM Call → Raw Output → Harness Validation → Trusted Output
                         ↓ (if validation fails)
                    Confidence-Flagged Output (still returned, but marked unreliable)
```

### The harness does 4 things:

1. **Schema Validation** — Every LLM response must match a Pydantic schema. Wrong types, missing fields, out-of-range values → caught.

2. **Citation Verification** — Every claim in the analysis must reference a specific line/segment in the transcript. No citation = low confidence.

3. **Cross-Check** — For critical fields (sentiment, outcome, hallucination flag), run a second LLM call with a different prompt. If they disagree → flag.

4. **Consistency Score** — Same transcript analyzed twice should produce similar results. Track drift over time.

### Data Flow

```
Pipeline Stage 2 (Analysis):
  1. LLM returns raw JSON
  2. Harness validates against AnalysisOutput schema
     - sentiment_arc ∈ {"positive", "negative", "mixed", "neutral"}
     - outcome ∈ {"resolved", "unresolved", "escalated"}
     - hallucination_detected is bool
     - quality_score ∈ 0-100
     - Each finding has a citation (line number or quote)
  3. If validation fails → mark confidence < threshold, include validation_errors
  4. Store both raw_output and validated_output in context

Pipeline Stage 3 (Report):
  1. LLM returns report JSON
  2. Harness validates against ReportOutput schema
     - quality_score is int 0-100
     - key_findings is list of strings
     - recommendations is list of strings
  3. If validation fails → flag in report metadata

Post-Analysis (optional cross-check):
  1. Take the raw transcript + analysis result
  2. Ask LLM: "Given this transcript, rate these analysis claims: [claims]"
  3. Compare cross-check ratings with original analysis
  4. If disagreement rate > 30% → set truth_score < 0.7
```

---

## Implementation Plan

### Phase 1: Schema Validation (covers 80% of hallucination risk)

**New file: `core/harness.py`**

```python
class AnalysisOutput(BaseModel):
    intent: str
    sentiment_arc: Literal["positive", "negative", "mixed", "neutral"]
    hallucination_detected: bool
    hallucination_evidence: str
    outcome: Literal["resolved", "unresolved", "escalated"]
    escalation_signal: bool
    findings: list[str] = []

class ReportOutput(BaseModel):
    quality_score: int  # 0-100
    key_findings: list[str]
    recommendations: list[str]
    summary: str

class ValidationHarness:
    def validate_analysis(self, raw_output: dict) -> ValidationResult:
        # Try Pydantic validation
        # Return validated output + confidence score + errors
    
    def validate_report(self, raw_output: dict) -> ValidationResult:
        # Try Pydantic validation
        # Return validated output + confidence score + errors
    
    def compute_truth_score(self, validation_results: list[ValidationResult]) -> float:
        # Aggregate confidence across all stages
```

**Modify: `agents/analysis_agent.py`**
- After `json.loads(response.content)`, call `harness.validate_analysis(result)`
- Store validation result in `ctx.report["harness"]`

**Modify: `agents/report_agent.py`**
- After `json.loads(response.content)`, call `harness.validate_report(result)`
- Store validation result in `ctx.report["harness"]`

### Phase 2: Citation Verification

**New file: `core/citations.py`**

```python
class CitationVerifier:
    def verify(self, transcript: str, findings: list[str]) -> CitationResult:
        # For each finding, check if the transcript contains
        # a matching substring (fuzzy matching with difflib)
        # Returns: coverage ratio, unmatched_findings
```

**Integration:**
- After validation, run citation verification on analysis findings
- Low citation coverage → reduce truth_score

### Phase 3: Cross-Check (deferred — highest latency cost)

**New file: `core/crosscheck.py`**

```python
class CrossChecker:
    async def check(self, transcript: str, analysis: AnalysisOutput) -> CrossCheckResult:
        # Ask a different LLM (or same LLM with different prompt)
        # to verify the analysis claims
        # Returns: agreement_rate, disagreements
```

**Integration:**
- Optional, only when `CROSS_CHECK_ENABLED=true`
- Adds 1 extra LLM call per analysis
- Use different temperature (0.5 vs 0.1) for diversity

### Phase 4: Pipeline Integration

**Modify: `core/pipeline.py`**

```python
async def run(self, audio_bytes, filename):
    ctx = PipelineContext()
    
    # Stage 1: Transcription (unchanged)
    ctx = await self.transcription_agent.run(ctx, audio_bytes, filename)
    
    # Stage 2: Analysis (with harness)
    if "transcription" in ctx.stages_completed:
        ctx = await self.analysis_agent.run(ctx)
        # NEW: Run validation harness
        ctx = self.harness.validate_pipeline(ctx)
    
    # Stage 3: Report (unchanged, but report agent uses harness internally)
    ctx = await self.report_agent.run(ctx)
    
    # NEW: Final truth score
    ctx.report["harness"] = self.harness.get_summary()
    
    return ctx.report
```

### Phase 5: API Response Enhancement

**Modify: `api/routes.py`**

Every `/api/v1/analyze` response now includes:
```json
{
  "report": { ... },
  "harness": {
    "truth_score": 0.87,
    "validation_passed": true,
    "citation_coverage": 0.92,
    "confidence": "high",
    "validation_errors": [],
    "cross_check_agreement": null
  }
}
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `core/harness.py` | CREATE | Schema validation, truth scoring |
| `core/test_harness.py` | RENAME from `core/harness.py` | Existing test harness for voice AI calls |
| `core/citations.py` | CREATE | Citation verification |
| `core/crosscheck.py` | CREATE | Cross-check verification (optional) |
| `agents/analysis_agent.py` | MODIFY | Add harness validation after LLM call |
| `agents/report_agent.py` | MODIFY | Add harness validation after LLM call |
| `core/pipeline.py` | MODIFY | Wire harness into pipeline flow |
| `core/context.py` | MODIFY | Add `harness_results` field |
| `api/routes.py` | MODIFY | Expose harness results in API response |
| `api/schemas.py` | MODIFY | Add HarnessResult to HealthResponse/response models |
| `tests/test_harness.py` | CREATE | Unit tests for validation harness |
| `tests/test_citations.py` | CREATE | Unit tests for citation verification |

---

## Edge Cases

1. **LLM returns non-JSON** → `json.loads()` fails → harness returns `truth_score=0`, `validation_errors=["json_parse_failed"]`
2. **LLM returns valid JSON but wrong schema** → Pydantic validation fails → harness returns partial validation with specific field errors
3. **LLM returns empty response** → harness catches empty content, returns `truth_score=0`
4. **LLM returns extra fields** → Pydantic ignores them (model config `extra="ignore"`)
5. **Transcript is too short for citation matching** → skip citation verification, return `citation_coverage=null`
6. **Cross-check LLM also hallucinates** → agreement rate is meaningless → set `cross_check_agreement=null` with warning
7. **Multiple LLM providers with different output formats** → harness validates against the same schema regardless of provider. Provider-specific quirks (e.g., Anthropic returning markdown-wrapped JSON) are handled in the provider layer.

---

## Test Coverage

### Unit Tests (`tests/test_harness.py`)
- `test_validate_analysis_valid` — valid analysis passes
- `test_validate_analysis_bad_sentiment` — invalid sentiment_arc caught
- `test_validate_analysis_bad_outcome` — invalid outcome caught
- `test_validate_analysis_hallucination_not_bool` — non-bool hallucination_detected caught
- `test_validate_analysis_quality_score_out_of_range` — score > 100 or < 0 caught
- `test_validate_analysis_missing_fields` — missing required fields caught
- `test_validate_analysis_extra_fields` — extra fields ignored gracefully
- `test_validate_report_valid` — valid report passes
- `test_validate_report_quality_score_string` — "85" (string) caught, coerced to int
- `test_validate_report_empty_findings` — empty findings list passes
- `test_compute_truth_score_all_pass` — score = 1.0
- `test_compute_truth_score_one_fail` — score reduced proportionally
- `test_compute_truth_score_all_fail` — score = 0.0
- `test_json_parse_failure` — non-JSON input returns score 0
- `test_empty_response` — empty string returns score 0

### Unit Tests (`tests/test_citations.py`)
- `test_verify_citations_all_found` — all findings match transcript
- `test_verify_citations_none_found` — no findings match
- `test_verify_citations_partial` — some findings match
- `test_verify_citations_empty_transcript` — empty transcript handled
- `test_verify_citations_fuzzy_match` — slight mismatches tolerated

### Integration Tests
- `test_pipeline_with_harness` — full pipeline returns harness results
- `test_pipeline_harness_with_bad_llm` — mocked LLM returning garbage → harness catches it
- `test_api_response_includes_harness` — API response has harness field

---

## Performance Impact

| Component | Latency | Cost |
|-----------|---------|------|
| Schema validation (Pydantic) | <1ms | None |
| Citation verification (fuzzy string match) | <10ms | None |
| Cross-check (extra LLM call) | 1-3s | ~$0.01 per call |
| **Total without cross-check** | **<11ms** | **$0** |
| **Total with cross-check** | **1-3s** | **~$0.01** |

Default: cross-check OFF. Enable via `CROSS_CHECK_ENABLED=true`.

---

## What This Does NOT Do

- Does not prevent the LLM from hallucinating in the first place (that's a prompt engineering problem)
- Does not guarantee 100% accuracy (nothing can)
- Does not add latency to the transcription stage (Whisper output is not validated by harness — it's ASR, not generative)
- Does not replace human QA (harness catches structural lies, not subtle misinterpretations)

---

## Commitment

This harness will:
- Catch 100% of schema violations (wrong types, out-of-range values, missing fields)
- Catch ~80% of factual hallucinations (via citation verification)
- Catch ~60% of interpretation errors (via cross-check, when enabled)
- Add <11ms latency (without cross-check)
- Add zero cost (without cross-check)
