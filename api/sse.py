import json
from typing import AsyncGenerator
from core.pipeline import VoiceScopePipeline
from core.context import PipelineContext
from utils.logger import logger
from storage.monitoring import MonitoringStore
from storage.cost_store import CostStore


async def stream_analysis(audio_bytes: bytes, filename: str) -> AsyncGenerator[str, None]:
    pipeline = VoiceScopePipeline()
    ctx = PipelineContext()

    yield f"data: {json.dumps({'event': 'started', 'run_id': ctx.run_id})}\n\n"

    try:
        ctx = await pipeline.transcription_agent.run(ctx, audio_bytes, filename)
        yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'transcription', 'run_id': ctx.run_id})}\n\n"

        if "transcription" in ctx.stages_completed:
            ctx = await pipeline.analysis_agent.run(ctx)
            yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'analysis', 'run_id': ctx.run_id})}\n\n"

        ctx = await pipeline.report_agent.run(ctx)
        yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'report', 'run_id': ctx.run_id})}\n\n"

        report = ctx.report or {}
        report["run_id"] = ctx.run_id
        report["raw_transcript"] = ctx.raw_transcript
        report["transcript_speakers"] = ctx.transcript_speakers

        try:
            await MonitoringStore().log_run(report, ctx.report.get("harness") if isinstance(ctx.report, dict) else None)
        except Exception:
            logger.exception("[SSE] failed to log run")
        try:
            await CostStore().log_cost(
                run_id=ctx.run_id,
                provider=report.get("provider", {}).get("name") if isinstance(report.get("provider"), dict) else None,
                model=report.get("provider", {}).get("model") if isinstance(report.get("provider"), dict) else None,
                input_tokens=report.get("provider", {}).get("input_tokens", 0) if isinstance(report.get("provider"), dict) else 0,
                output_tokens=report.get("provider", {}).get("output_tokens", 0) if isinstance(report.get("provider"), dict) else 0,
                cost_usd=report.get("provider", {}).get("cost_usd", 0.0) if isinstance(report.get("provider"), dict) else 0.0,
            )
        except Exception:
            logger.exception("[SSE] failed to log cost")

        yield f"data: {json.dumps({'event': 'complete', 'result': report})}\n\n"
    except Exception:
        logger.exception("[SSE] stream_analysis failed")
        yield f"data: {json.dumps({'event': 'error', 'detail': 'Analysis failed'})}\n\n"
