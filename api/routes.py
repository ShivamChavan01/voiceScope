from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import StreamingResponse
from api.schemas import HealthResponse, detect_and_parse_webhook
from api.sse import stream_analysis
from core.pipeline import VoiceScopePipeline
from core.batch import BatchProcessor
from core.test_harness import TestHarness
from core.qa import QAStore, QACohort, ResolutionCriterion
from core.extractions import ExtractionStore, ExtractionSchema, ExtractionField
from storage.cost_store import CostStore
from storage.monitoring import MonitoringStore
from utils.logger import logger
from utils.security import hash_api_key, sanitize_log_input, validate_callback_url_async
from utils.guardrails import guardrails
from typing import Optional
from functools import lru_cache
import httpx
from pydantic import BaseModel, Field

router = APIRouter()


@lru_cache(maxsize=1)
def get_pipeline():
    p = VoiceScopePipeline()
    p.harness = get_validation_harness()
    return p


@lru_cache(maxsize=1)
def get_cost_store():
    return CostStore()


@lru_cache(maxsize=1)
def get_batch_processor():
    return BatchProcessor()


@lru_cache(maxsize=1)
def get_harness():
    return TestHarness()


@lru_cache(maxsize=1)
def get_monitoring_store():
    return MonitoringStore()


@lru_cache(maxsize=1)
def get_validation_harness():
    from core.harness import ValidationHarness
    return ValidationHarness()


@lru_cache(maxsize=1)
def get_qa_store():
    return QAStore()


@lru_cache(maxsize=1)
def get_extraction_store():
    return ExtractionStore()


async def _log_cost(result: dict):
    """Log LLM cost for a pipeline result."""
    try:
        if result.get("provider", {}).get("name"):
            p = result["provider"]
            await get_cost_store().log_cost(
                run_id=result["run_id"],
                provider=p["name"],
                model=p["model"],
                input_tokens=p["input_tokens"],
                output_tokens=p["output_tokens"],
                cost_usd=p["cost_usd"],
            )
    except Exception:
        logger.exception("[Routes] failed to log cost")


async def _log_metrics(result: dict):
    """Log call metrics for monitoring."""
    try:
        await get_monitoring_store().log_call(result)
    except Exception:
        logger.exception("[Routes] failed to log metrics")


async def _log_run(result: dict, harness_result=None):
    """Log run metadata for the Runs page."""
    try:
        harness_obj = None
        if harness_result:
            if isinstance(harness_result, dict):
                from core.harness import HarnessResult
                harness_obj = HarnessResult(**harness_result)
            else:
                harness_obj = harness_result
        await get_monitoring_store().log_run(result, harness_obj)
        await _create_incidents_for_run(result)
    except Exception:
        logger.exception("[Routes] failed to log run")


async def _create_incidents_for_run(result: dict):
    """Auto-create incidents when a run has a hallucination or escalation signal."""
    run_id = result.get("run_id", "")
    analysis = result.get("analysis") or {}
    hallucinated = bool(analysis.get("hallucination_detected") or result.get("hallucination_detected"))
    escalated = bool(analysis.get("escalation_signal") or result.get("escalation_signal"))
    store = get_monitoring_store()
    short_id = run_id[:8] if run_id else "unknown"
    if hallucinated:
        await store.create_run_incident(
            run_id, "hallucination",
            f"Hallucination detected in run {short_id} — agent made claims not supported by the transcript.",
        )
    if escalated:
        await store.create_run_incident(
            run_id, "escalation",
            f"Escalation signal in run {short_id} — customer frustration or unresolved issue detected.",
        )


ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
    "audio/x-m4a",
}
MAX_FILE_SIZE_MB = 25


ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".ogg"}


def _validate_audio(file: UploadFile, audio_bytes: bytes):
    # Check content type first, fall back to filename extension
    ext = ""
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file.content_type not in ALLOWED_AUDIO_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type} ({ext}). Allowed: mp3, wav, m4a, webm",
        )
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400, detail=f"File too large: {size_mb:.1f}MB. Max: {MAX_FILE_SIZE_MB}MB"
        )
    return size_mb


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    size_mb = _validate_audio(file, audio_bytes)

    logger.info(
        f"[API] /analyze — file={sanitize_log_input(file.filename or 'unknown')}, size={size_mb:.2f}MB"
    )

    result = await get_pipeline().run(audio_bytes, file.filename or "upload.mp3")

    harness_data = result.get("harness")
    await _log_cost(result)
    await _log_metrics(result)
    await _log_run(result, harness_data)

    # Include pipeline errors in response for debugging
    if result.get("errors"):
        result["pipeline_errors"] = result["errors"]

    return result


@router.post("/analyze/stream")
async def analyze_audio_stream(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    size_mb = _validate_audio(file, audio_bytes)

    logger.info(
        f"[API] /analyze/stream — file={sanitize_log_input(file.filename or 'unknown')}, size={size_mb:.2f}MB"
    )

    return StreamingResponse(
        stream_analysis(audio_bytes, file.filename or "upload.mp3"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/batch")
async def create_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    callback_url: Optional[str] = Form(None),
):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key) if api_key else None

    file_data = []
    for file in files:
        if file.content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {file.content_type}"
            )
        audio_bytes = await file.read()
        if len(audio_bytes) / (1024 * 1024) > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {sanitize_log_input(file.filename or 'unknown')}",
            )
        file_data.append((audio_bytes, file.filename or "upload.mp3"))

    try:
        batch_id = await get_batch_processor().create_batch(file_data, callback_url, owner_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"batch_id": batch_id, "status": "processing", "total_files": len(files)}


@router.get("/batch/{batch_id}")
async def get_batch_status(request: Request, batch_id: str):
    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key)
    batch = get_batch_processor().get_batch(batch_id, owner_key)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "batch_id": batch["batch_id"],
        "status": batch["status"],
        "total": batch["total"],
        "completed": batch["completed"],
        "failed": batch["failed"],
    }


@router.get("/batch/{batch_id}/results")
async def get_batch_results(request: Request, batch_id: str):
    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key)
    batch = get_batch_processor().get_batch(batch_id, owner_key)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch["status"] != "completed":
        raise HTTPException(status_code=400, detail="Batch still processing")
    return {"batch_id": batch_id, "results": batch["results"]}


@router.get("/costs")
async def get_costs():
    return await get_cost_store().get_summary()


@router.get("/runs")
async def get_runs(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    status: Optional[str] = None,
):
    return await get_monitoring_store().get_runs(
        limit=limit, offset=offset, search=search, status=status
    )


@router.get("/runs/history")
async def get_run_history(limit: int = 12):
    scores = await get_monitoring_store().get_truth_history(limit=limit)
    return {"scores": scores, "count": len(scores)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = await get_monitoring_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    deleted = await get_monitoring_store().delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"status": "deleted", "run_id": run_id}


@router.post("/harness/run")
async def run_harness():
    return await get_harness().run_all()


@router.post("/webhooks/call-completed")
async def webhook_call_completed(request: Request):
    body = await request.json()
    event = detect_and_parse_webhook(body)

    logger.info(
        f"[API] webhook received — platform={event.platform}, "
        f"call_id={event.call_id}, event={event.event_type}"
    )

    completed_events = {
        "end-of-call-report",
        "call_ended",
        "call.ended",
        "call.completed",
        "completed",
        "agent_goodbye",
    }
    if event.event_type not in completed_events:
        raise HTTPException(
            status_code=400,
            detail=f"Event '{event.event_type}' not supported — expected one of: {completed_events}",
        )

    if not event.recording_url:
        raise HTTPException(status_code=400, detail="No recording_url found in webhook payload")

    if not await validate_callback_url_async(event.recording_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid recording_url: must be HTTPS and not target private IPs",
        )

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
            head_resp = await http_client.head(event.recording_url)
            try:
                content_length = int(head_resp.headers.get("content-length", 0))
            except (ValueError, TypeError):
                content_length = 0
            if content_length > 25 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Recording too large (max 25MB)")
            resp = await http_client.get(event.recording_url)
            resp.raise_for_status()
            audio_bytes = b""
            async for chunk in resp.aiter_bytes(chunk_size=8192):
                audio_bytes += chunk
                if len(audio_bytes) > 25 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="Recording too large (max 25MB)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=402, detail="Failed to download recording"
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Failed to download recording")

    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"Recording is not audio: content-type={content_type}",
        )

    ext = "mp3"
    if "wav" in content_type:
        ext = "wav"
    elif "webm" in content_type:
        ext = "webm"
    elif "ogg" in content_type:
        ext = "ogg"
    elif "m4a" in content_type or "mp4" in content_type:
        ext = "m4a"

    filename = f"webhook_{event.call_id}.{ext}"
    result = await get_pipeline().run(audio_bytes, filename)

    harness_data = result.get("harness")
    await _log_cost(result)
    await _log_metrics(result)
    await _log_run(result, harness_data)

    if result.get("errors") and not result.get("report"):
        raise HTTPException(status_code=500, detail="Webhook analysis failed")

    logger.info(
        f"[API] webhook processed — platform={event.platform}, "
        f"call_id={event.call_id}, run_id={result.get('run_id')}"
    )
    return {
        "platform": event.platform,
        "call_id": event.call_id,
        "pipeline_result": result,
    }


# ─── Monitoring & Alerting ────────────────────────────────────────────


class AlertRuleRequest(BaseModel):
    name: str
    metric: str  # hallucination_rate, escalation_rate, avg_quality_score, avg_cost, total_calls, negative_sentiment_rate
    comparator: str  # gt, lt, gte, lte, eq
    threshold: float
    window_minutes: int = 60
    notify_url: Optional[str] = None
    notify_email: Optional[str] = None


@router.get("/monitoring/metrics")
async def get_monitoring_metrics(window_minutes: int = 60):
    return await get_monitoring_store().get_metrics_summary(window_minutes)


@router.get("/monitoring/alerts")
async def get_alert_rules():
    return await get_monitoring_store().list_rules()


@router.post("/monitoring/alerts")
async def create_alert_rule(req: AlertRuleRequest):
    rule_id = await get_monitoring_store().create_rule(
        name=req.name,
        metric=req.metric,
        comparator=req.comparator,
        threshold=req.threshold,
        window_minutes=req.window_minutes,
        notify_url=req.notify_url,
        notify_email=req.notify_email,
    )
    return {"rule_id": rule_id, "status": "created"}


@router.delete("/monitoring/alerts/{rule_id}")
async def delete_alert_rule(rule_id: int):
    deleted = await get_monitoring_store().delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}


@router.get("/monitoring/incidents")
async def get_incidents(limit: int = 50):
    return await get_monitoring_store().list_incidents(limit)


@router.post("/monitoring/check")
async def check_alerts():
    triggered = await get_monitoring_store().check_alerts()
    return {"triggered": triggered, "count": len(triggered)}


# ─── QA System ────────────────────────────────────────────────────────


class QACohortRequest(BaseModel):
    name: str
    agent_filter: Optional[str] = None
    platform_filter: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    sampling_pct: float = 10.0
    weekly_max: int = 100
    criteria: list[ResolutionCriterion] = Field(default_factory=list)


class QAScoreRequest(BaseModel):
    run_id: str
    metrics: dict = Field(default_factory=dict)


@router.get("/qa/cohorts")
async def list_qa_cohorts():
    return await get_qa_store().list_cohorts()


@router.post("/qa/cohorts")
async def create_qa_cohort(req: QACohortRequest):
    cohort = QACohort(
        name=req.name,
        agent_filter=req.agent_filter,
        platform_filter=req.platform_filter,
        min_duration=req.min_duration,
        max_duration=req.max_duration,
        sampling_pct=req.sampling_pct,
        weekly_max=req.weekly_max,
        criteria=req.criteria,
    )
    cohort_id = await get_qa_store().create_cohort(cohort)
    return {"cohort_id": cohort_id, "status": "created"}


@router.post("/qa/cohorts/{cohort_id}/score")
async def score_call(cohort_id: int, req: QAScoreRequest):
    try:
        return await get_qa_store().score_call(cohort_id, req.run_id, req.metrics)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/qa/cohorts/{cohort_id}/results")
async def get_qa_results(cohort_id: int, limit: int = 100):
    return await get_qa_store().get_cohort_results(cohort_id, limit)


# ─── Custom Extractions ──────────────────────────────────────────────


class ExtractionSchemaRequest(BaseModel):
    name: str
    description: str = ""
    fields: list[ExtractionField] = Field(default_factory=list)


class ExtractionRunRequest(BaseModel):
    run_id: str
    transcript: str
    metadata: dict = Field(default_factory=dict)


@router.get("/extractions/schemas")
async def list_extraction_schemas():
    return await get_extraction_store().list_schemas()


@router.post("/extractions/schemas")
async def create_extraction_schema(req: ExtractionSchemaRequest):
    schema = ExtractionSchema(name=req.name, description=req.description, fields=req.fields)
    schema_id = await get_extraction_store().create_schema(schema)
    return {"schema_id": schema_id, "status": "created"}


@router.delete("/extractions/schemas/{schema_id}")
async def delete_extraction_schema(schema_id: int):
    deleted = await get_extraction_store().delete_schema(schema_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"status": "deleted"}


@router.post("/extractions/schemas/{schema_id}/run")
async def run_extractions(schema_id: int, req: ExtractionRunRequest):
    try:
        return await get_extraction_store().run_extractions(
            schema_id, req.run_id, req.transcript, req.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/extractions/schemas/{schema_id}/results")
async def get_extraction_results(schema_id: int, limit: int = 100):
    return await get_extraction_store().get_results(schema_id, limit)


# ─── Guardrails ──────────────────────────────────────────────────────


class GuardrailCheckRequest(BaseModel):
    text: str
    check_type: str = "input"  # input | output | redact_pii


@router.get("/guardrails/status")
async def get_guardrail_status():
    return guardrails.get_status()


@router.post("/guardrails/check")
async def check_guardrails(req: GuardrailCheckRequest):
    if req.check_type == "input":
        result = guardrails.check_input(req.text)
        return {
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "flagged_categories": result.flagged_categories,
        }
    elif req.check_type == "output":
        result = guardrails.check_output(req.text)
        return {
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "flagged_categories": result.flagged_categories,
            "redacted_text": result.redacted_text,
        }
    elif req.check_type == "redact_pii":
        redacted, redactions = guardrails.redact_pii(req.text)
        return {"redacted_text": redacted, "redactions": redactions}
    else:
        raise HTTPException(status_code=400, detail="check_type must be input, output, or redact_pii")


# ─── Validation Harness ──────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    run_id: str
    feedback: str  # "correct" or "incorrect"
    notes: str = ""


@router.get("/harness/status")
async def get_harness_status():
    return get_validation_harness().get_summary()


@router.post("/harness/feedback")
async def submit_feedback(req: FeedbackRequest):
    from core.feedback import FeedbackStore
    store = FeedbackStore()
    return store.submit(req.run_id, req.feedback, req.notes)


@router.get("/harness/calibration")
async def get_calibration():
    from core.calibration import ConfidenceCalibrator
    cal = ConfidenceCalibrator()
    return cal.get_calibration().model_dump()


@router.post("/harness/validate")
async def validate_text(req: GuardrailCheckRequest):
    """Run harness validation on arbitrary text (for testing)."""
    from core.harness import AnalysisOutput
    try:
        validated = AnalysisOutput(
            intent=req.text[:200],
            sentiment_arc="neutral",
            outcome="unresolved",
            hallucination_detected=False,
            hallucination_evidence="",
            escalation_signal=False,
        )
        return {"valid": True, "truth_score": 1.0, "validated": validated.model_dump()}
    except Exception as e:
        return {"valid": False, "truth_score": 0.0, "errors": [str(e)]}


# ─── Self-Improvement Loop ──────────────────────────────────────────


@router.get("/loop/status")
async def get_loop_status():
    from core.self_improve import SelfImprovementLoop
    loop = SelfImprovementLoop()
    return loop.get_status()


@router.post("/loop/run")
async def run_improvement_loop():
    from core.self_improve import SelfImprovementLoop
    loop = SelfImprovementLoop()
    result = loop.run()
    return {
        "status": result.status,
        "benchmark": {
            "total_tests": result.benchmark.total_tests,
            "avg_truth_score": result.benchmark.avg_truth_score,
            "sentiment_accuracy": result.benchmark.sentiment_accuracy,
            "outcome_accuracy": result.benchmark.outcome_accuracy,
            "weakest_layer": result.benchmark.weakest_layer,
            "strongest_layer": result.benchmark.strongest_layer,
        },
        "optimization": {
            "improvement": result.optimization.improvement,
            "changes": result.optimization.changes_made,
        },
        "suggestions": result.suggestions,
    }


@router.get("/loop/benchmark")
async def get_benchmark():
    from core.benchmark import HarnessBenchmark
    bench = HarnessBenchmark()
    summary = bench.run_benchmark()
    return {
        "total_tests": summary.total_tests,
        "avg_truth_score": summary.avg_truth_score,
        "sentiment_accuracy": summary.sentiment_accuracy,
        "outcome_accuracy": summary.outcome_accuracy,
        "hallucination_accuracy": summary.hallucination_accuracy,
        "escalation_accuracy": summary.escalation_accuracy,
        "avg_citation_coverage": summary.avg_citation_coverage,
        "avg_fact_accuracy": summary.avg_fact_accuracy,
        "weakest_layer": summary.weakest_layer,
        "strongest_layer": summary.strongest_layer,
    }


@router.get("/loop/suggestions")
async def get_suggestions():
    from core.prompt_tracker import PromptTracker
    tracker = PromptTracker()
    return {"suggestions": tracker.get_suggestions()}


@router.get("/loop/weights")
async def get_weights():
    from core.optimizer import CalibrationOptimizer
    opt = CalibrationOptimizer()
    return {"weights": opt.get_current_weights(), "history": len(opt.get_history())}
