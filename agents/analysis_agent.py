from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from core.knowledge_base import KnowledgeBase
from storage.chroma_store import ChromaStore
from utils.logger import logger
import json


CLAIMS_PROMPT = """
You are extracting factual claims from a customer service call transcript.
List any promises, commitments, or guarantees made by the support agent during this call.
Include only explicit statements like "we will", "you'll get", "I can guarantee", "refunds take X days", etc.

Transcript:
{transcript}

Return ONLY valid JSON: a JSON array of strings, each being one claim.
Example: ["We will process your refund within 5 business days", "Your replacement will ship tomorrow"]
If no claims are found, return an empty array: []
"""


ANALYSIS_PROMPT = """
You are an expert voice AI quality analyst. Analyze the following customer-agent call transcript and return a structured JSON object.

Transcript:
{transcript}

Similar past calls for context (RAG):
{rag_context}

Knowledge base policy context for claim verification:
{kb_context}

Instructions for hallucination detection:
- The "Knowledge base policy context" section contains claims extracted from the transcript alongside relevant business policy.
- If a claim contradicts documented policy, set hallucination_detected to true and quote the specific contradiction in hallucination_evidence.
- If no knowledge base context is available, perform transcript-only analysis: flag claims that seem factually inconsistent within the transcript itself.
- Only flag genuine contradictions, not minor wording differences.

Return ONLY valid JSON with these exact keys:
{{
  "intent": "short description of what the caller wanted",
  "sentiment_arc": "positive | negative | mixed | neutral",
  "hallucination_detected": true | false,
  "hallucination_evidence": "quote the specific claim and the contradicting policy if hallucination detected, else null",
  "outcome": "resolved | unresolved | escalated",
  "escalation_signal": true | false
}}
"""


class AnalysisAgent:
    """
    Agent 2 — LLM-powered analysis of transcript.
    Uses RAG context from ChromaDB for similar past calls.
    Uses KnowledgeBase for policy-grounded hallucination detection.
    Populates: intent, sentiment_arc, hallucination_detected, outcome, escalation_signal
    """

    def __init__(self, chroma_store: ChromaStore, knowledge_base: KnowledgeBase | None = None):
        self.provider = ProviderRegistry.get()
        self.chroma = chroma_store
        self.kb = knowledge_base

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.raw_transcript:
            ctx.add_error("analysis", "No transcript available — skipping analysis")
            return ctx

        logger.info(f"[AnalysisAgent] run_id={ctx.run_id}")

        rag_context = await self._get_rag_context(ctx.raw_transcript)

        kb_context = "No knowledge base available — performing transcript-only analysis."
        if self.kb and self.kb.available:
            try:
                claims = await self._extract_claims(ctx.raw_transcript)
                if claims:
                    kb_context = await self._get_kb_context(claims)
                    logger.info(
                        f"[AnalysisAgent] KB check: {len(claims)} claims, "
                        f"policy context length={len(kb_context)}"
                    )
                else:
                    kb_context = "No agent claims found in transcript."
                    logger.info("[AnalysisAgent] KB check: no claims extracted")
            except Exception as e:
                logger.warning(f"[AnalysisAgent] KB extraction failed — {e}")

        prompt = ANALYSIS_PROMPT.format(
            transcript=ctx.raw_transcript,
            rag_context=rag_context or "No similar past calls found.",
            kb_context=kb_context,
        )

        try:
            response = await self.provider.complete(
                prompt=prompt, temperature=0.1, response_format={"type": "json_object"}
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

    async def _extract_claims(self, transcript: str) -> list[str]:
        prompt = CLAIMS_PROMPT.format(transcript=transcript)
        response = await self.provider.complete(
            prompt=prompt, temperature=0.0, response_format={"type": "json_object"}
        )
        result = json.loads(response.content)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "claims" in result:
            return result["claims"]
        return []

    async def _get_kb_context(self, claims: list[str]) -> str:
        parts: list[str] = []
        for claim in claims:
            results = await self.kb.query(claim, n_results=2)
            if results:
                policy_text = "\n".join(results)
                parts.append(f'Claim: "{claim}"\nRelevant Policy:\n{policy_text}')
        return "\n---\n".join(parts) if parts else "No relevant policy found for extracted claims."

    async def _get_rag_context(self, transcript: str) -> str:
        try:
            results = await self.chroma.query(transcript, n_results=3)
            if not results:
                return ""
            return "\n---\n".join(results)
        except Exception as e:
            logger.warning(f"[AnalysisAgent] RAG query failed — {e}")
            return ""
