from llm_providers.registry import ProviderRegistry
from core.context import PipelineContext
from core.knowledge_base import KnowledgeBase
from storage.chroma_store import ChromaStore
from utils.logger import logger
import json
import re


CHUNK_WORD_LIMIT = 1000
ANALYSIS_WORD_THRESHOLD = 4000

_SPEAKER_PATTERN = re.compile(
    r"^((?:Agent|Customer|User|Bot|Rep|Support|Caller|Agent|Representative|CSR)\s*:)",
    re.IGNORECASE | re.MULTILINE,
)

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
  "intent": "max 8 words describing what the caller wanted (e.g. 'cancel subscription', 'technical support for router')",
  "sentiment_arc": "positive | negative | mixed | neutral",
  "hallucination_detected": true | false,
  "hallucination_evidence": "quote the specific claim and the contradicting policy if hallucination detected, else null",
  "outcome": "resolved | unresolved | escalated",
  "escalation_signal": true | false
}}
"""

SUMMARIZATION_PROMPT = """
Summarize this segment of a customer support call in 3-4 sentences.
Preserve: promises made, complaints raised, resolution status.

Transcript segment:
{chunk}

Return ONLY valid JSON: {{"summary": "..."}}
"""


def _count_words(text: str) -> int:
    return len(text.split())


def _split_by_speaker_turns(transcript: str) -> list[str]:
    lines = transcript.splitlines()
    turns: list[str] = []
    current_turn: list[str] = []

    for line in lines:
        if _SPEAKER_PATTERN.match(line.strip()):
            if current_turn:
                turns.append("\n".join(current_turn))
            current_turn = [line]
        else:
            current_turn.append(line)

    if current_turn:
        turns.append("\n".join(current_turn))

    return turns


def _chunk_turns(turns: list[str], max_words: int) -> list[str]:
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_words = 0

    for turn in turns:
        turn_words = _count_words(turn)
        if current_words + turn_words > max_words and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_words = 0
        current_chunk.append(turn)
        current_words += turn_words

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class AnalysisAgent:
    """
    Agent 2 — LLM-powered analysis of transcript.
    Uses RAG context from ChromaDB for similar past calls.
    Uses KnowledgeBase for policy-grounded hallucination detection.
    Supports hierarchical summarization for transcripts over 4000 words.
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

        ctx.word_count = _count_words(ctx.raw_transcript)
        transcript_for_analysis = ctx.raw_transcript

        if ctx.word_count > ANALYSIS_WORD_THRESHOLD:
            logger.info(
                f"[AnalysisAgent] transcript is {ctx.word_count} words — "
                f"using hierarchical summarization"
            )
            transcript_for_analysis = await self._hierarchical_summarize(ctx.raw_transcript, ctx)
            logger.info(
                f"[AnalysisAgent] summarized {ctx.chunk_count} chunks "
                f"into {ctx.word_count} words (original: {_count_words(ctx.raw_transcript)} words)"
            )
        else:
            ctx.chunk_count = None

        rag_context = await self._get_rag_context(ctx.raw_transcript)

        kb_context = "No knowledge base available — performing transcript-only analysis."
        if self.kb and self.kb.available:
            try:
                claims = await self._extract_claims(transcript_for_analysis)
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
            transcript=transcript_for_analysis,
            rag_context=rag_context or "No similar past calls found.",
            kb_context=kb_context,
        )

        try:
            response = await self.provider.complete(
                prompt=prompt, temperature=0.1, response_format={"type": "json_object"}
            )

            result = json.loads(response.content)

            intent = result.get("intent", "")
            if len(intent.split()) > 8:
                intent = " ".join(intent.split()[:8])
            ctx.intent = intent
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

    async def _hierarchical_summarize(self, transcript: str, ctx: PipelineContext) -> str:
        turns = _split_by_speaker_turns(transcript)
        if not turns:
            logger.warning(
                "[AnalysisAgent] no speaker turns found — falling back to raw transcript"
            )
            return transcript

        chunks = _chunk_turns(turns, CHUNK_WORD_LIMIT)
        ctx.chunk_count = len(chunks)
        logger.info(
            f"[AnalysisAgent] split into {ctx.chunk_count} chunks "
            f"(turns={len(turns)}, limit={CHUNK_WORD_LIMIT} words/chunk)"
        )

        summaries: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            try:
                summary = await self._summarize_chunk(chunk)
                summaries.append(summary)
                logger.info(f"[AnalysisAgent] chunk {i}/{ctx.chunk_count} summarized")
            except Exception as e:
                logger.warning(f"[AnalysisAgent] chunk {i} summarization failed — {e}")
                summaries.append(chunk)

        combined = "\n\n".join(summaries)
        ctx.word_count = _count_words(combined)
        return combined

    async def _summarize_chunk(self, chunk: str) -> str:
        prompt = SUMMARIZATION_PROMPT.format(chunk=chunk)
        response = await self.provider.complete(
            prompt=prompt, temperature=0.0, response_format={"type": "json_object"}
        )
        result = json.loads(response.content)
        if isinstance(result, dict) and "summary" in result:
            summary: str = result["summary"]
            return summary
        return str(result)

    async def _extract_claims(self, transcript: str) -> list[str]:
        prompt = CLAIMS_PROMPT.format(transcript=transcript)
        response = await self.provider.complete(
            prompt=prompt, temperature=0.0, response_format={"type": "json_object"}
        )
        result = json.loads(response.content)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "claims" in result:
            claims: list[str] = result["claims"]
            return claims
        return []

    async def _get_kb_context(self, claims: list[str]) -> str:
        if not self.kb:
            return "No knowledge base available."
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
