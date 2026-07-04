"""
Speaker Agent — classifies which speaker is the agent vs customer.
Uses the LLM to analyze transcript context and assign roles.
Populates: ctx.transcript_speakers with role labels
"""

import json
from core.context import PipelineContext
from llm_providers.registry import ProviderRegistry
from utils.logger import logger


SPEAKER_PROMPT = """You are analyzing a call transcript. The transcript has been split into segments by speaker number.

Here are the speaker segments:
{segments}

Your task: identify which speaker number is the AGENT (support/agent representative) and which is the CUSTOMER.

Look for clues like:
- Who introduces themselves or their department
- Who says "how may I help you" or similar service phrases
- Who is asking the questions vs providing information
- Who controls the flow of the conversation

Return ONLY a JSON object mapping speaker numbers to roles:
{{"speaker_roles": {{"0": "agent", "1": "customer"}}}}

If there are more than 2 speakers, label the extra ones as "other".
If you cannot determine roles, label the first speaker as "agent" and the second as "customer"."""


class SpeakerAgent:
    """
    Classifies speaker roles (agent vs customer) using the LLM.
    Runs after transcription when multiple speakers are detected.
    """

    def __init__(self):
        self.provider = ProviderRegistry.get()

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.transcript_speakers or len(ctx.transcript_speakers) < 2:
            if ctx.transcript_speakers:
                ctx.transcript_speakers[0]["role"] = "agent"
                ctx.transcript_speakers[0]["label"] = "Agent"
            return ctx

        unique_speakers = set(s["speaker"] for s in ctx.transcript_speakers)
        if len(unique_speakers) < 2:
            ctx.transcript_speakers[0]["role"] = "agent"
            ctx.transcript_speakers[0]["label"] = "Agent"
            return ctx

        segments_text = []
        for seg in ctx.transcript_speakers:
            segments_text.append(f"Speaker {seg['speaker']}: {seg['text'][:200]}")
        segments_str = "\n".join(segments_text[:30])

        prompt = SPEAKER_PROMPT.format(segments=segments_str)

        try:
            response = await self.provider.complete(
                prompt=prompt,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.content)
            roles = result.get("speaker_roles", {})

            for seg in ctx.transcript_speakers:
                spk = str(seg["speaker"])
                role = roles.get(spk, "other")
                seg["role"] = role
                seg["label"] = role.capitalize() if role != "other" else "Other"

            logger.info(f"[SpeakerAgent] classified {len(unique_speakers)} speakers: {roles}")

        except Exception as e:
            logger.warning(f"[SpeakerAgent] classification failed, defaulting: {e}")
            for seg in ctx.transcript_speakers:
                spk = seg["speaker"]
                seg["role"] = "agent" if spk == 0 else "customer"
                seg["label"] = "Agent" if spk == 0 else "Customer"

        return ctx
