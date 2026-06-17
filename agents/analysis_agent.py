from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from storage.chroma_store import ChromaStore
from utils.logger import logger
import json


ANALYSIS_PROMPT = """
You are an expert voice AI quality analyst. Analyze the following customer-agent call transcript and return a structured JSON object.

Transcript:
{transcript}

Similar past calls for context (RAG):
{rag_context}

Return ONLY valid JSON with these exact keys:
{{
  "intent": "short description of what the caller wanted",
  "sentiment_arc": "positive | negative | mixed | neutral",
  "hallucination_detected": true | false,
  "hallucination_evidence": "quote the specific claim if hallucination detected, else null",
  "outcome": "resolved | unresolved | escalated",
  "escalation_signal": true | false
}}
"""


class AnalysisAgent:
    """
    Agent 2 — LLM-powered analysis of transcript.
    Uses RAG context from ChromaDB for similar past calls.
    Populates: intent, sentiment_arc, hallucination_detected, outcome, escalation_signal
    """

    def __init__(self, chroma_store: ChromaStore):
        self.provider = ProviderRegistry.get()
        self.chroma = chroma_store

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.raw_transcript:
            ctx.add_error("analysis", "No transcript available — skipping analysis")
            return ctx

        logger.info(f"[AnalysisAgent] run_id={ctx.run_id}")

        rag_context = await self._get_rag_context(ctx.raw_transcript)

        prompt = ANALYSIS_PROMPT.format(
            transcript=ctx.raw_transcript,
            rag_context=rag_context or "No similar past calls found."
        )

        try:
            response = await self.provider.complete(
                prompt=prompt,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.content)

            ctx.intent = result.get("intent")
            ctx.sentiment_arc = result.get("sentiment_arc")
            ctx.hallucination_detected = result.get("hallucination_detected")
            ctx.hallucination_evidence = result.get("hallucination_evidence")
            ctx.outcome = result.get("outcome")
            ctx.escalation_signal = result.get("escalation_signal")
            ctx.mark_stage("analysis")

            logger.info(f"[AnalysisAgent] done — intent={ctx.intent}, outcome={ctx.outcome}")

        except Exception as e:
            ctx.add_error("analysis", str(e))
            logger.error(f"[AnalysisAgent] failed — {e}")

        return ctx

    async def _get_rag_context(self, transcript: str) -> str:
        try:
            results = await self.chroma.query(transcript, n_results=3)
            if not results:
                return ""
            return "\n---\n".join(results)
        except Exception as e:
            logger.warning(f"[AnalysisAgent] RAG query failed — {e}")
            return ""
