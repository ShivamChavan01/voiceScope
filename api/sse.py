import json
from typing import AsyncGenerator

from core.context import PipelineContext
from core.pipeline import VoiceScopePipeline
from storage.cost_store import CostStore
from storage.monitoring import MonitoringStore
from utils.logger import logger


async def stream_analysis(audio_bytes: bytes, filename: str) -> AsyncGenerator[str, None]:
    ctx = PipelineContext()

    yield f"data: {json.dumps({'event': 'started', 'run_id': ctx.run_id})}\n\n"

    try:
        pipeline = VoiceScopePipeline()
        ctx = await pipeline.transcription_agent.run(ctx, audio_bytes, filename)
        if "transcription" in ctx.stages_completed:
            yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'transcription', 'run_id': ctx.run_id})}\n\n"

        if "transcription" in ctx.stages_completed:
            ctx = await pipeline.attribute_speakers(ctx)
            ctx = await pipeline.assess_reliability(ctx)
            ctx = await pipeline.analysis_agent.run(ctx)
            if "analysis" in ctx.stages_completed:
                yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'analysis', 'run_id': ctx.run_id})}\n\n"

        if "analysis" in ctx.stages_completed:
            ctx = await pipeline.report_agent.run(ctx)
        else:
            ctx.report = {"run_id": ctx.run_id, "analysis": {}}
        if "report" in ctx.stages_completed:
            yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'report', 'run_id': ctx.run_id})}\n\n"

        harness_result = pipeline.harness.validate_pipeline(ctx)
        yield f"data: {json.dumps({'event': 'stage_complete', 'stage': 'harness', 'run_id': ctx.run_id})}\n\n"

        report = pipeline.finalize_result(ctx, harness_result)

        try:
            await MonitoringStore().log_run(report, harness_result)
        except Exception:
            logger.exception("[SSE] failed to log run")
            yield f"data: {json.dumps({'event': 'error', 'detail': 'Evaluation completed but the report could not be saved. Check storage before retrying.'})}\n\n"
            return
        try:
            provider_obj = report.get("provider")
            provider_data = provider_obj if isinstance(provider_obj, dict) else {}
            await CostStore().log_cost(
                run_id=ctx.run_id,
                provider=str(provider_data.get("name") or "unknown"),
                model=str(provider_data.get("model") or "unknown"),
                input_tokens=int(provider_data.get("input_tokens", 0)),
                output_tokens=int(provider_data.get("output_tokens", 0)),
                cost_usd=float(provider_data.get("cost_usd", 0.0)),
            )
        except Exception:
            logger.exception("[SSE] failed to log cost")

        yield f"data: {json.dumps({'event': 'complete', 'result': report})}\n\n"
    except Exception:
        logger.exception("[SSE] stream_analysis failed")
        yield f"data: {json.dumps({'event': 'error', 'detail': 'Analysis failed'})}\n\n"
