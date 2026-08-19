import json
import os

import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

from unittest.mock import AsyncMock, MagicMock, patch

from core.context import PipelineContext

# ─── Transcription Agent Tests ────────────────────────────────────────


class TestTranscriptionAgent:
    @pytest.mark.asyncio
    async def test_transcription_populates_context(self):
        from agents.transcription_agent import TranscriptionAgent

        agent = TranscriptionAgent()
        mock_result = MagicMock()
        mock_result.transcript = "Hello, how can I help?"
        mock_result.speakers = [{"speaker": 0, "text": "Hello"}]
        mock_result.language = "en"
        mock_result.duration_seconds = 10.5

        with patch("agents.transcription_agent.STTRegistry") as mock_registry:
            mock_provider = AsyncMock()
            mock_provider.transcribe = AsyncMock(return_value=mock_result)
            mock_provider.name = "deepgram"
            mock_registry.get.return_value = mock_provider

            ctx = PipelineContext()
            ctx = await agent.run(ctx, b"audio", "test.mp3")

        assert ctx.raw_transcript == "Hello, how can I help?"
        assert ctx.language_detected == "en"
        assert ctx.audio_duration_seconds == 10.5
        assert "transcription" in ctx.stages_completed

    @pytest.mark.asyncio
    async def test_transcription_error_adds_error(self):
        from agents.transcription_agent import TranscriptionAgent

        agent = TranscriptionAgent()
        with patch("agents.transcription_agent.STTRegistry") as mock_registry:
            mock_provider = AsyncMock()
            mock_provider.transcribe = AsyncMock(side_effect=Exception("STT failed"))
            mock_provider.name = "deepgram"
            mock_registry.get.return_value = mock_provider

            ctx = PipelineContext()
            ctx = await agent.run(ctx, b"audio", "test.mp3")

        assert ctx.raw_transcript is None
        assert len(ctx.errors) > 0


# ─── Speaker Agent Tests ──────────────────────────────────────────────


class TestSpeakerAgent:
    @pytest.mark.asyncio
    async def test_single_speaker_gets_agent_role(self):
        from agents.speaker_agent import SpeakerAgent

        with patch("agents.speaker_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = SpeakerAgent()
        ctx = PipelineContext()
        ctx.transcript_speakers = [{"speaker": 0, "text": "Hello, I'm the agent"}]

        ctx = await agent.run(ctx)

        assert ctx.transcript_speakers[0]["role"] == "agent"
        assert ctx.transcript_speakers[0]["label"] == "Agent"

    @pytest.mark.asyncio
    async def test_no_speakers(self):
        from agents.speaker_agent import SpeakerAgent

        with patch("agents.speaker_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = SpeakerAgent()
        ctx = PipelineContext()
        ctx.transcript_speakers = None

        ctx = await agent.run(ctx)

        assert ctx.transcript_speakers is None

    @pytest.mark.asyncio
    async def test_same_speaker_twice_gets_agent(self):
        from agents.speaker_agent import SpeakerAgent

        with patch("agents.speaker_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = SpeakerAgent()
        ctx = PipelineContext()
        ctx.transcript_speakers = [
            {"speaker": 0, "text": "Hello"},
            {"speaker": 0, "text": "Hello again"},
        ]

        ctx = await agent.run(ctx)

        assert ctx.transcript_speakers[0]["role"] == "agent"

    @pytest.mark.asyncio
    async def test_multi_speaker_classification(self):
        from agents.speaker_agent import SpeakerAgent

        with patch("agents.speaker_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = SpeakerAgent()
        ctx = PipelineContext()
        ctx.transcript_speakers = [
            {"speaker": 0, "text": "How can I help you today?"},
            {"speaker": 1, "text": "I need help with my order"},
            {"speaker": 0, "text": "Let me look into that"},
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "speaker_roles": {"0": "agent", "1": "customer"}
        })

        agent.provider = AsyncMock()
        agent.provider.complete = AsyncMock(return_value=mock_response)

        ctx = await agent.run(ctx)

        assert ctx.transcript_speakers[0]["role"] == "agent"
        assert ctx.transcript_speakers[1]["role"] == "customer"

    @pytest.mark.asyncio
    async def test_llm_failure_defaults_to_agent_customer(self):
        from agents.speaker_agent import SpeakerAgent

        with patch("agents.speaker_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = SpeakerAgent()
        agent.provider = AsyncMock()
        agent.provider.complete = AsyncMock(side_effect=Exception("LLM error"))

        ctx = PipelineContext()
        ctx.transcript_speakers = [
            {"speaker": 0, "text": "Agent speaking"},
            {"speaker": 1, "text": "Customer speaking"},
        ]

        ctx = await agent.run(ctx)

        assert ctx.transcript_speakers[0]["role"] == "agent"
        assert ctx.transcript_speakers[1]["role"] == "customer"


# ─── Analysis Agent Tests ─────────────────────────────────────────────


class TestAnalysisAgent:
    def _make_agent(self):
        from agents.analysis_agent import AnalysisAgent

        mock_chroma = AsyncMock()
        mock_chroma.query = AsyncMock(return_value=["past call context"])
        mock_kb = MagicMock()
        mock_kb.available = False
        with patch("agents.analysis_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            return AnalysisAgent(chroma_store=mock_chroma, knowledge_base=mock_kb)

    @pytest.mark.asyncio
    async def test_no_transcript_skips_analysis(self):
        agent = self._make_agent()
        ctx = PipelineContext()
        ctx.raw_transcript = None

        ctx = await agent.run(ctx)

        assert ctx.intent is None
        assert len(ctx.errors) > 0

    @pytest.mark.asyncio
    async def test_analysis_populates_context(self):
        agent = self._make_agent()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "intent": "cancel subscription",
            "sentiment_arc": "negative",
            "hallucination_detected": False,
            "hallucination_evidence": None,
            "outcome": "resolved",
            "escalation_signal": False,
            "findings": ["customer requested cancel"],
        })
        agent.provider = AsyncMock()
        agent.provider.name = "openai"
        agent.provider.complete = AsyncMock(return_value=mock_response)

        from llm_providers.registry import ProviderRegistry
        ProviderRegistry._instances["openai"] = agent.provider

        ctx = PipelineContext()
        ctx.raw_transcript = "Agent: How can I help?\nCustomer: I want to cancel."
        ctx.stages_completed = ["transcription"]

        ctx = await agent.run(ctx)

        assert ctx.intent == "cancel subscription"
        assert ctx.sentiment_arc == "negative"
        assert ctx.outcome == "resolved"
        assert "analysis" in ctx.stages_completed

    @pytest.mark.asyncio
    async def test_rag_and_claims_run_in_parallel(self):
        import asyncio

        agent = self._make_agent()
        mock_kb = MagicMock()
        mock_kb.available = True
        agent.kb = mock_kb

        order = []
        async def slow_rag(_transcript):
            order.append("rag")
            await asyncio.sleep(0.05)
            return "rag context"

        async def slow_claims(_transcript):
            order.append("claims")
            await asyncio.sleep(0.05)
            return ["claim 1"]

        agent._get_rag_context = AsyncMock(side_effect=slow_rag)
        agent._extract_claims = AsyncMock(side_effect=slow_claims)
        agent._get_kb_context = AsyncMock(return_value="policy text")
        agent._summarize_chunk = AsyncMock()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "intent": "help request",
            "sentiment_arc": "neutral",
            "hallucination_detected": False,
            "hallucination_evidence": None,
            "outcome": "unresolved",
            "escalation_signal": False,
            "findings": ["customer requested help"],
        })
        agent.provider = AsyncMock()
        agent.provider.name = "openai"
        agent.provider.complete = AsyncMock(return_value=mock_response)
        from llm_providers.registry import ProviderRegistry
        ProviderRegistry._instances["openai"] = agent.provider

        ctx = PipelineContext()
        ctx.raw_transcript = "Agent: How can I help?"

        await agent.run(ctx)

        # Both started before either completed → overlapped
        assert order == ["rag", "claims"]
        agent._get_rag_context.assert_awaited_once()
        agent._extract_claims.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chunk_summaries_preserve_order(self):
        import asyncio

        agent = self._make_agent()

        async def slow_summary(chunk: str) -> str:
            await asyncio.sleep(0.02)
            return f"summary:{chunk[:5]}"

        agent._summarize_chunk = slow_summary

        chunks = ["chunk-one-aaaa", "chunk-two-bbbb", "chunk-three-cccc"]
        result = await agent._summarize_chunks_parallel(chunks, max_concurrency=2)

        assert result == ["summary:chunk", "summary:chunk", "summary:chunk"]

    def test_count_words(self):
        from agents.analysis_agent import _count_words

        assert _count_words("hello world") == 2
        assert _count_words("") == 0
        assert _count_words("one two three four five") == 5

    def test_split_by_speaker_turns(self):
        from agents.analysis_agent import _split_by_speaker_turns

        transcript = "Agent: Hello\nCustomer: Hi\nAgent: How can I help?"
        turns = _split_by_speaker_turns(transcript)
        assert len(turns) == 3

    def test_chunk_turns(self):
        from agents.analysis_agent import _chunk_turns

        turns = ["Agent: " + "word " * 500, "Customer: " + "word " * 500]
        chunks = _chunk_turns(turns, max_words=600)
        assert len(chunks) == 2


# ─── Report Agent Tests ───────────────────────────────────────────────


class TestReportAgent:
    @pytest.mark.asyncio
    async def test_report_populates_context(self):
        from agents.report_agent import ReportAgent

        mock_chroma = AsyncMock()
        mock_chroma.store = AsyncMock()
        with patch("agents.report_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = ReportAgent(chroma_store=mock_chroma)

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "executive_summary": "Call about subscription cancellation.",
            "quality_score": 80,
            "key_findings": ["Customer wanted to cancel"],
            "recommendations": ["Offer retention discount"],
        })
        mock_response.provider = "openai"
        mock_response.model = "gpt-4o"
        mock_response.cost_usd = 0.01
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50

        agent.provider = AsyncMock()
        agent.provider.name = "openai"
        agent.provider.complete = AsyncMock(return_value=mock_response)

        from llm_providers.registry import ProviderRegistry
        ProviderRegistry._instances["openai"] = agent.provider

        ctx = PipelineContext()
        ctx.intent = "cancel subscription"
        ctx.sentiment_arc = "negative"
        ctx.outcome = "resolved"
        ctx.raw_transcript = "Agent: How can I help?\nCustomer: Cancel my sub."

        ctx = await agent.run(ctx)

        assert ctx.report is not None
        assert ctx.report["report"]["quality_score"] == 80
        assert "report" in ctx.stages_completed
        mock_chroma.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_persists_evidence_fields(self):
        from agents.report_agent import ReportAgent

        mock_chroma = AsyncMock()
        mock_chroma.store = AsyncMock()
        with patch("agents.report_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = ReportAgent(chroma_store=mock_chroma)

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "executive_summary": "Hallucination detected.",
            "quality_score": 55,
            "key_findings": ["Agent promised same-day refund"],
            "recommendations": ["Coach the agent on refund policy"],
        })
        mock_response.provider = "groq"
        mock_response.model = "openai/gpt-oss-120b"
        mock_response.cost_usd = 0.004
        mock_response.input_tokens = 200
        mock_response.output_tokens = 120

        agent.provider = AsyncMock()
        agent.provider.name = "groq"
        agent.provider.complete = AsyncMock(return_value=mock_response)

        from llm_providers.registry import ProviderRegistry
        ProviderRegistry._instances["groq"] = agent.provider

        ctx = PipelineContext()
        ctx.intent = "refund request"
        ctx.sentiment_arc = "negative"
        ctx.outcome = "unresolved"
        ctx.hallucination_detected = True
        ctx.hallucination_evidence = "Agent guaranteed a same-day refund."
        ctx.policy_evidence = "Claim: same-day refund\nRelevant Policy:\nAgents cannot guarantee same-day refunds."

        ctx = await agent.run(ctx)

        assert ctx.report["analysis"]["hallucination_evidence"] == "Agent guaranteed a same-day refund."
        assert ctx.report["analysis"]["policy_evidence"].startswith("Claim:")

    @pytest.mark.asyncio
    async def test_report_error_sets_error_report(self):
        from agents.report_agent import ReportAgent

        mock_chroma = AsyncMock()
        with patch("agents.report_agent.ProviderRegistry") as mock_reg:
            mock_reg.get.return_value = AsyncMock()
            agent = ReportAgent(chroma_store=mock_chroma)
        agent.provider = AsyncMock()
        agent.provider.complete = AsyncMock(side_effect=Exception("LLM error"))

        ctx = PipelineContext()
        ctx = await agent.run(ctx)

        assert ctx.report is not None
        assert "error" in ctx.report
        assert len(ctx.errors) > 0
