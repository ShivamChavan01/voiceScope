import asyncio
import json
import os
import re
from functools import lru_cache
from typing import Literal, Optional
from urllib.parse import urlparse

import aiohttp
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from api.schemas import HealthResponse, detect_and_parse_webhook
from api.sse import stream_analysis
from api.stt_routes import router as stt_router
from core.batch import BatchProcessor
from core.demo_seed import reset_demo_runs, seed_demo_runs
from core.extractions import ExtractionField, ExtractionSchema, ExtractionStore
from core.knowledge_store import KnowledgeStore
from core.pipeline import VoiceScopePipeline
from core.stt_recording import download_recording
from core.qa import QACohort, QAStore, ResolutionCriterion
from core.test_harness import TestHarness
from storage.cost_store import CostStore
from storage.monitoring import AssessmentFilter, MonitoringStore
from utils.guardrails import guardrails
from utils.logger import logger
from utils.security import hash_api_key, sanitize_log_input, validate_callback_url_async

router = APIRouter()
router.include_router(stt_router)

BOLNA_API_KEY = os.getenv("BOLNA_API_KEY") or ""
BOLNA_RECORDINGS_API = "https://api.bolna.ai/recordings"


def _recording_candidates(event) -> list[tuple[str, dict]]:
    """Ordered (url, headers) candidates for downloading the recording.

    Bolna recording URLs are served from api.bolna.ai and require a
    Bearer API key; the stable endpoint regenerates a fresh signed URL
    on every request, so prefer it over any URL carried in the payload.
    """
    candidates: list[tuple[str, dict]] = []
    if event.platform == "bolna" and event.call_id:
        auth = {"Authorization": f"Bearer {BOLNA_API_KEY}"} if BOLNA_API_KEY else {}
        candidates.append((f"{BOLNA_RECORDINGS_API}/call/{event.call_id}", auth))
        candidates.append((f"{BOLNA_RECORDINGS_API}/transfer/{event.call_id}", auth))
    if event.recording_url:
        headers: dict = {}
        if BOLNA_API_KEY and urlparse(event.recording_url).hostname == "api.bolna.ai":
            headers["Authorization"] = f"Bearer {BOLNA_API_KEY}"
        candidates.append((event.recording_url, headers))
    return candidates


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


@lru_cache(maxsize=1)
def get_knowledge_store():
    return KnowledgeStore()


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
    except Exception:
        logger.exception("[Routes] failed to log run")
        raise HTTPException(status_code=503, detail='Evaluation completed but the report could not be saved. Check storage before retrying.')
    try:
        await _create_incidents_for_run(result)
    except Exception:
        logger.exception('[Routes] failed to create incidents for saved run')


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
MAX_WEBHOOK_BODY_BYTES = 2 * 1024 * 1024  # 2MB webhook payload cap


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


@router.post("/demo/seed")
async def demo_seed():
    return await seed_demo_runs(get_monitoring_store())


@router.post("/demo/reset")
async def demo_reset():
    return await reset_demo_runs(get_monitoring_store())


class PolicyRuleRequest(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["no_same_day_refund_guarantee", "honor_escalation_request"]
    text: str = Field(min_length=1, max_length=5000)
    enabled: bool = Field(default=True, strict=True)


@router.get("/policies/rules")
async def list_policy_rules():
    from core.policy_store import PolicyStore

    return [rule.model_dump() for rule in await PolicyStore().list_rules()]


@router.post("/policies/rules")
async def save_policy_rule(req: PolicyRuleRequest):
    from pydantic import ValidationError
    from core.policy_store import PolicyStore
    from core.reliability import PolicyRule

    try:
        rule = PolicyRule(**req.model_dump())
    except ValidationError:
        raise HTTPException(status_code=422, detail="Policy text must explicitly express the selected supported rule")
    saved = await PolicyStore().upsert_rule(rule)
    return saved.model_dump()


@router.delete("/policies/rules/{rule_id}")
async def remove_policy_rule(rule_id: str):
    from core.policy_store import PolicyStore

    if not await PolicyStore().delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Policy rule not found")
    return {"status": "deleted"}


@router.post("/demo/reliability")
async def seed_reliability_demo():
    from core.staging import demo_enabled
    if demo_enabled():
        from core.staging_demo import seed_staging_demo
        return await seed_staging_demo()
    from core.reliability_demo import demo_scenarios
    from core.speech_diagnostics import SpeechDiagnostics

    scenarios = demo_scenarios()
    for result in scenarios:
        result.setdefault("speech_diagnostics", SpeechDiagnostics(
            limitations=["Synthetic transcript scenario; speech timings were not measured."]
        ).model_dump())
        await get_monitoring_store().log_run(result)
    return {"seeded": len(scenarios), "run_ids": [result["run_id"] for result in scenarios]}


@router.post('/demo/staging')
async def seed_free_staging():
    from core.staging import demo_enabled
    from core.staging_demo import seed_staging_demo

    if not demo_enabled():
        raise HTTPException(status_code=404, detail='Synthetic staging is not enabled')
    return await seed_staging_demo()


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    size_mb = _validate_audio(file, audio_bytes)

    logger.info(
        f"[API] /analyze — size={size_mb:.2f}MB"
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
        f"[API] /analyze/stream — size={size_mb:.2f}MB"
    )

    return StreamingResponse(
        stream_analysis(audio_bytes, file.filename or "upload.mp3"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


class TranscriptRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=60000)


@router.post("/analyze-text")
async def analyze_transcript(body: TranscriptRequest):
    """Transcript-only analysis — no audio/STT needed (UI testing, debugging)."""
    logger.info(f"[API] /analyze-text — chars={len(body.transcript)}")

    result = await get_pipeline().run_from_transcript(body.transcript)

    harness_data = result.get("harness")
    await _log_cost(result)
    await _log_metrics(result)
    await _log_run(result, harness_data)

    if result.get("errors"):
        result["pipeline_errors"] = result["errors"]

    return result


@router.get("/status")
async def backend_status():
    """Backend + LLM provider status for the UI (no secrets)."""
    from llm_providers.registry import ProviderRegistry

    primary = os.getenv("LLM_PROVIDER", "openai")
    return {
        "service": "voicescope",
        "llm_provider": primary,
        "llm_model": os.getenv("LLM_MODEL") or None,
        "llm_backups_configured": ProviderRegistry._backup_names(primary),
        "providers": ProviderRegistry.list_providers(),
    }


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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=2_147_483_647),
    search: Optional[str] = None,
    status: Optional[Literal['completed', 'partial', 'failed']] = None,
    assessment: Optional[AssessmentFilter] = None,
):
    return await get_monitoring_store().get_runs(
        limit=limit, offset=offset, search=search, status=status, assessment=assessment
    )


@router.get("/runs/summary")
async def get_run_summary():
    return await get_monitoring_store().get_run_summary()


@router.get("/runs/history")
async def get_run_history(limit: int = Query(12, ge=1, le=200)):
    scores = await get_monitoring_store().get_truth_history(limit=limit)
    return {"scores": scores, "count": len(scores)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request, response: Response):
    run = await get_monitoring_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    from api.stt_routes import attach_stt_report
    if request.headers.get('X-STT-Review') == '1':
        response.headers['Cache-Control'] = 'no-store'
    return attach_stt_report(run, request)


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    deleted = await get_monitoring_store().delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    from storage.stt_reviews import STTReviewStore
    STTReviewStore().delete_run(run_id)
    return {"status": "deleted", "run_id": run_id}


@router.post("/harness/run")
async def run_harness():
    return await get_harness().run_all()


@router.post("/webhooks/call-completed")
async def webhook_call_completed(request: Request):
    raw_body = bytearray()
    async for chunk in request.stream():
        if len(raw_body) + len(chunk) > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail=f'Webhook payload too large (max {MAX_WEBHOOK_BODY_BYTES} bytes)')
        raw_body.extend(chunk)
    try:
        body = json.loads(raw_body, parse_constant=_reject_json_constant)
    except ValueError:
        raise HTTPException(status_code=400, detail="Webhook payload is not valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail='Webhook payload must be an object')
    try:
        event = detect_and_parse_webhook(body)
    except (ValidationError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail='Invalid webhook execution fields')
    if event.platform == 'bolna':
        source_id = body.get('id')
        if isinstance(source_id, bool) or not isinstance(source_id, (str, int)) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', str(source_id)) or str(source_id).lower() in ('none', 'null'):
            raise HTTPException(status_code=400, detail='A valid Bolna execution ID is required')
    if request.headers.get('X-Webhook-Key') and event.platform != 'bolna':
        raise HTTPException(status_code=403, detail='This webhook credential is restricted to Bolna events')
    from core.staging import qa_agent_id
    if qa_agent_id():
        from core.staging_qa import validate_qa_event
        validate_qa_event(event)

    logger.info(
        f"[API] webhook received — platform={event.platform}"
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

    if event.platform == 'bolna':
        from storage.webhook_receipts import WebhookReceipts
        receipts = WebhookReceipts()
        state, value = receipts.claim(event.call_id)
        if state == 'completed':
            run = await get_monitoring_store().get_run(value)
            if not run:
                raise HTTPException(status_code=409, detail='Previously processed call report is unavailable. Inspect storage before retrying.')
            result = {'platform': event.platform, 'call_id': event.call_id, 'pipeline_result': run['evaluation']}
            return _webhook_response(result, request)
        if state == 'processing':
            raise HTTPException(status_code=409, detail='Call evaluation is already processing. Retry later.', headers={'Retry-After': '10'})
        try:
            result = await _process_webhook(event)
            run_id = result['pipeline_result'].get('run_id')
            if not run_id or not await get_monitoring_store().get_run(run_id):
                raise HTTPException(status_code=503, detail='Call report could not be persisted. Retry later.')
            receipts.complete(event.call_id, value, run_id)
            return _webhook_response(result, request)
        except (Exception, asyncio.CancelledError):
            receipts.release(event.call_id, value)
            raise
    return await _process_webhook(event)


def _reject_json_constant(value: str):
    raise ValueError('Non-finite JSON numbers are not supported')


def _webhook_response(result: dict, request: Request) -> dict:
    if getattr(request.state, 'operator_authenticated', False):
        return result
    evaluation = result['pipeline_result']
    return {'platform': result['platform'], 'call_id': result['call_id'],
            'run_id': evaluation['run_id'], 'status': evaluation.get('status')}


async def _process_webhook(event):
    from core.staging import qa_agent_id
    if qa_agent_id():
        from core.staging_qa import process_qa_call
        return {'platform': event.platform, 'call_id': event.call_id,
                'pipeline_result': await process_qa_call(event)}
    if event.platform == "bolna" and event.transcript and event.transcript.strip():
        result = await get_pipeline().run_from_transcript(event.transcript)
        result.setdefault("transcript_meta", {})["duration_seconds"] = (
            event.duration_ms / 1000 if event.duration_ms is not None else None
        )
        result["transcript_source"] = "bolna"
        return await _save_webhook_result(event, result)

    candidates = _recording_candidates(event)
    if not candidates:
        raise HTTPException(status_code=400, detail="No recording_url found in webhook payload")

    audio_bytes = b""
    content_type = ""
    network_error = False
    validation_rejected = 0
    for url, headers in candidates:
        if not await validate_callback_url_async(url):
            logger.warning("[Webhook] recording URL rejected by SSRF validation")
            validation_rejected += 1
            continue
        try:
            audio_bytes, content_type = await download_recording(url, headers)
            break
        except ValueError as exc:
            if 'not audio' in str(exc):
                raise HTTPException(status_code=400, detail='Recording is not audio')
            if '25 MB' in str(exc):
                raise HTTPException(status_code=400, detail='Recording too large (max 25MB)')
            logger.warning('[Webhook] recording download rejected')
            continue
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as exc:
            logger.warning(f'[Webhook] recording download failed: {type(exc).__name__}')
            network_error = True
            continue
    else:
        if validation_rejected == len(candidates):
            raise HTTPException(
                status_code=400,
                detail="Invalid recording_url: must be HTTPS and not target private IPs",
            )
        raise HTTPException(
            status_code=502 if network_error else 402,
            detail="Failed to download recording",
        )

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

    return await _save_webhook_result(event, result)


async def _save_webhook_result(event, result: dict):
    from core.speech_diagnostics import bolna_speech_diagnostics

    if event.platform == "bolna":
        from core.stt_sources import bolna_transcript
        if event.transcript and event.transcript.strip():
            result["stt_source"] = bolna_transcript(event.transcript).model_dump(mode="json")
        result["speech_diagnostics"] = bolna_speech_diagnostics(event.raw).model_dump()
    result["platform"] = event.platform
    result["source_call"] = {"call_id": event.call_id, "platform": event.platform, **event.metadata}
    harness_data = result.get("harness")
    await _log_cost(result)
    await _log_metrics(result)
    await _log_run(result, harness_data)

    if result.get("status") == 'failed' or result.get("errors") and not result.get("report"):
        raise HTTPException(status_code=500, detail="Webhook analysis failed")

    logger.info(
        f"[API] webhook processed — platform={event.platform}, "
        f"run_id={result.get('run_id')}"
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
async def get_incidents(limit: int = Query(50, ge=1, le=200)):
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
async def get_qa_results(cohort_id: int, limit: int = Query(100, ge=1, le=200)):
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
async def get_extraction_results(schema_id: int, limit: int = Query(100, ge=1, le=200)):
    return await get_extraction_store().get_results(schema_id, limit)


# ─── Knowledge Base ─────────────────────────────────────────────────


class KnowledgeEntryRequest(BaseModel):
    title: str = ""
    content: str


@router.get("/knowledge")
async def list_knowledge():
    return await get_knowledge_store().list_entries()


@router.post("/knowledge")
async def add_knowledge(req: KnowledgeEntryRequest):
    try:
        entry_id = await get_knowledge_store().add_entry(req.title, req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Rebuild the pipeline KB index so new policies take effect immediately.
    try:
        get_pipeline().kb.reload()
    except Exception:
        logger.exception("[Routes] failed to reload knowledge base")
    return {"entry_id": entry_id, "status": "created"}


@router.delete("/knowledge/{entry_id}")
async def delete_knowledge(entry_id: int):
    deleted = await get_knowledge_store().delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    try:
        get_pipeline().kb.reload()
    except Exception:
        logger.exception("[Routes] failed to reload knowledge base")
    return {"status": "deleted"}


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
    from core.harness import AnalysisOutput, OutcomeType, SentimentType
    try:
        validated = AnalysisOutput(
            intent=req.text[:200],
            sentiment_arc=SentimentType.NEUTRAL,
            outcome=OutcomeType.UNRESOLVED,
            hallucination_detected=False,
            hallucination_evidence="",
            escalation_signal=False,
        )
        return {"valid": True, "truth_score": 1.0, "validated": validated.model_dump()}
    except Exception:
        return {"valid": False, "truth_score": 0.0, "errors": ['Validation failed; check the supplied text and schema']}


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
    try:
        summary = bench.run_benchmark()
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="Labeled benchmark data unavailable or invalid")
    return summary.model_dump(exclude={"results"})


@router.get("/loop/benchmark/reliability")
async def get_reliability_benchmark():
    from core.reliability_benchmark import run_reliability_benchmark
    try:
        return run_reliability_benchmark().model_dump()
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="Policy benchmark data unavailable or invalid")


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
