from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from utils.logger import logger
import json


EVAL_PROMPT = """
You are an expert evaluator for voice AI analysis quality. Score the following analysis on a scale of 1-5.

Transcript:
{transcript}

Analysis Results:
{analysis_data}

Report:
{report_data}

Return ONLY valid JSON with these exact keys:
{{
  "analysis_quality_score": <integer 1-5>,
  "analysis_quality_reasoning": "why this score",
  "confidence_score": <float 0.0-1.0>,
  "confidence_factors": ["factor1", "factor2"],
  "completeness_score": <integer 1-5>,
  "completeness_issues": ["issue1 or empty array"]
}}
"""


class EvalAgent:
    name = "evaluation"
    description = "LLM-as-judge evaluation of analysis quality"

    def __init__(self):
        self.provider = ProviderRegistry.get()

    async def run(self, ctx: PipelineContext, **kwargs) -> PipelineContext:
        if not ctx.raw_transcript or not ctx.report:
            ctx.add_error("eval", "Missing transcript or report for evaluation")
            return ctx

        logger.info(f"[EvalAgent] run_id={ctx.run_id}")

        analysis_data = {
            "intent": ctx.intent,
            "sentiment_arc": ctx.sentiment_arc,
            "hallucination_detected": ctx.hallucination_detected,
            "outcome": ctx.outcome,
            "escalation_signal": ctx.escalation_signal,
        }

        try:
            response = await self.provider.complete(
                prompt=EVAL_PROMPT.format(
                    transcript=ctx.raw_transcript[:2000],
                    analysis_data=json.dumps(analysis_data, indent=2),
                    report_data=json.dumps(ctx.report.get("report", {}), indent=2),
                ),
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            eval_data = json.loads(response.content)
            ctx.report["evaluation"] = eval_data
            ctx.mark_stage("evaluation")

            logger.info(
                f"[EvalAgent] done — quality={eval_data.get('analysis_quality_score')} confidence={eval_data.get('confidence_score')}"
            )

        except Exception as e:
            ctx.add_error("eval", str(e))
            logger.error(f"[EvalAgent] failed — {e}")

        return ctx

    def validate_input(self, ctx: PipelineContext) -> bool:
        return ctx.raw_transcript is not None and ctx.report is not None
