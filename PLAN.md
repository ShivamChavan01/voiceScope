# VoiceScope Post-Audit Fix Plan

## Context
Codebase audit found 4 critical gaps that would get flagged in an SDE-2 interview. This plan fixes them in priority order.

## Fix 1: Error handling for DB logging (routes.py:66-115)
**Problem:** `_log_cost`, `_log_metrics`, `_log_run` have zero try/except. If Supabase is down, every successful analysis returns 500 instead of the result.

**Fix:** Wrap each in try/except, log the error, continue. These are fire-and-forget logging — they should never kill the response.

**Files:** `api/routes.py:66-115`

## Fix 2: validate_pipeline() NoneType crash (harness.py:216)
**Problem:** `ctx.report.get("analysis", {})` raises AttributeError when `ctx.report` is None. Pipeline sets `ctx.report = {"audio_quality": ...}` early, but if report agent fails, `pipeline.py:69` sets it to `{"run_id": ..., "status": "failed"}` — no "analysis" key. The `.get()` works but `ctx.report` itself can be None if something upstream fails.

**Fix:** Add `ctx.report = ctx.report or {}` guard before the `.get()` call.

**Files:** `core/harness.py:214-216`

## Fix 3: Missing indexes on foreign key columns
**Problem:** `call_metrics.run_id` and `cost_logs.run_id` have no index. Queries filtering by run_id do full table scans.

**Fix:** Add two indexes to `SCHEMA_SQL`:
- `CREATE INDEX IF NOT EXISTS idx_call_metrics_run_id ON call_metrics(run_id);`
- `CREATE INDEX IF NOT EXISTS idx_cost_logs_run_id ON cost_logs(run_id);`

**Files:** `storage/db.py:110-114`

## Fix 4: End-to-end pipeline integration test
**Problem:** `VoiceScopePipeline.run()` is never tested as a unit. The entire core value chain has zero integration coverage. This is the single gap that invalidates "production-ready" claims.

**Fix:** Write `tests/test_pipeline_integration.py` that:
1. Mocks all 3 agents (transcription, analysis, report) to return valid outputs
2. Runs `VoiceScopePipeline.run()` with fake audio bytes
3. Asserts the result has: `run_id`, `harness.truth_score`, `harness.confidence`, `errors` list, `raw_transcript`
4. Asserts harness layers actually ran (truth_score is not None, confidence is one of the valid levels)
5. Tests the failure path: mock transcription agent to fail, assert pipeline still returns a result with errors and a fallback report

**Files:** `tests/test_pipeline_integration.py` (new)

## Verification
- `python3 -m py_compile` on all modified files
- `pytest tests/` — all existing + new tests pass
- `npm run lint` on frontend (no changes expected)
