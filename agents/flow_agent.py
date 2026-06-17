from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from utils.logger import logger
import json


FLOW_PROMPT = """
Analyze this transcript and extract the conversation flow structure.

Transcript:
{transcript}

Return ONLY valid JSON with these exact keys:
{{
  "speakers": ["Speaker 1", "Speaker 2"],
  "turns": [
    {{"speaker": "Speaker 1", "text": "exact text", "turn_number": 1}},
    {{"speaker": "Speaker 2", "text": "exact text", "turn_number": 2}}
  ],
  "total_turns": <integer>,
  "interruptions": <integer>,
  "avg_turn_duration_seconds": <float or null>,
  "talk_time_ratio": {{"Speaker 1": 0.5, "Speaker 2": 0.5}},
  "longest_monologue": {{"speaker": "Speaker 1", "text": "...", "word_count": <integer>}}
}}
"""


class FlowAgent:
    name = "conversation_flow"
    description = "Extracts speaker turns, interruptions, and talk-time ratio"

    def __init__(self):
        self.provider = ProviderRegistry.get()

    async def run(self, ctx: PipelineContext, **kwargs) -> PipelineContext:
        if not ctx.raw_transcript:
            ctx.add_error("flow", "No transcript available")
            return ctx

        logger.info(f"[FlowAgent] run_id={ctx.run_id}")

        try:
            response = await self.provider.complete(
                prompt=FLOW_PROMPT.format(transcript=ctx.raw_transcript),
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            flow_data = json.loads(response.content)
            ctx.report = ctx.report or {}
            ctx.report["conversation_flow"] = flow_data
            ctx.mark_stage("flow")

            logger.info(f"[FlowAgent] done — turns={flow_data.get('total_turns')}")

        except Exception as e:
            ctx.add_error("flow", str(e))
            logger.error(f"[FlowAgent] failed — {e}")

        return ctx

    def validate_input(self, ctx: PipelineContext) -> bool:
        return ctx.raw_transcript is not None and len(ctx.raw_transcript) > 50
