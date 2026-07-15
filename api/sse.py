import json
from typing import AsyncGenerator
from core.pipeline import VoiceScopePipeline
from core.context import PipelineContext
from utils.logger import logger


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

        yield f"data: {json.dumps({'event': 'complete', 'result': ctx.report})}\n\n"
    except Exception:
        logger.exception("[SSE] stream_analysis failed")
        yield f"data: {json.dumps({'event': 'error', 'detail': 'Analysis failed'})}\n\n"
