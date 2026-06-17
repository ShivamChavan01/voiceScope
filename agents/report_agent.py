from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from storage.chroma_store import ChromaStore
from utils.logger import logger
from datetime import datetime, timezone
import json


REPORT_PROMPT = """
You are a technical writer for a voice AI observability platform.

Given this analysis data, generate a concise structured report with an executive summary and recommendations.

Data:
{analysis_data}

Return ONLY valid JSON with these exact keys:
{{
  "executive_summary": "2-3 sentence summary of the call",
  "quality_score": <integer 0-100>,
  "key_findings": ["finding1", "finding2", "finding3"],
  "recommendations": ["recommendation1", "recommendation2"]
}}
"""


class ReportAgent:
    """
    Agent 3 — Assembles final report from all pipeline data.
    Stores report in ChromaDB for future RAG retrieval.
    Populates: ctx.report
    """

    def __init__(self, chroma_store: ChromaStore):
        self.provider = ProviderRegistry.get()
        self.chroma = chroma_store

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"[ReportAgent] run_id={ctx.run_id}")

        analysis_data = {
            "intent": ctx.intent,
            "sentiment_arc": ctx.sentiment_arc,
            "hallucination_detected": ctx.hallucination_detected,
            "hallucination_evidence": ctx.hallucination_evidence,
            "outcome": ctx.outcome,
            "escalation_signal": ctx.escalation_signal,
            "language": ctx.language_detected,
            "audio_duration_seconds": ctx.audio_duration_seconds,
        }

        try:
            response = await self.provider.complete(
                prompt=REPORT_PROMPT.format(analysis_data=json.dumps(analysis_data, indent=2)),
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            report_data = json.loads(response.content)

            ctx.report = {
                "run_id": ctx.run_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider": {
                    "name": response.provider,
                    "model": response.model,
                    "cost_usd": response.cost_usd,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
                "pipeline": {
                    "stages_completed": ctx.stages_completed,
                    "errors": ctx.errors
                },
                "transcript_meta": {
                    "language": ctx.language_detected,
                    "duration_seconds": ctx.audio_duration_seconds,
                    "char_count": len(ctx.raw_transcript or "")
                },
                "analysis": analysis_data,
                "report": report_data
            }

            ctx.mark_stage("report")

            if ctx.raw_transcript:
                await self.chroma.store(
                    doc_id=ctx.run_id,
                    text=ctx.raw_transcript,
                    metadata={"outcome": ctx.outcome, "intent": ctx.intent}
                )

            logger.info(f"[ReportAgent] done — quality_score={report_data.get('quality_score')}")

        except Exception as e:
            ctx.add_error("report", str(e))
            logger.error(f"[ReportAgent] failed — {e}")

        return ctx
