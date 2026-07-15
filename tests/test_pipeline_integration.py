import pytest
from unittest.mock import MagicMock, patch
from core.pipeline import VoiceScopePipeline


@pytest.fixture
def pipeline():
    with patch("core.pipeline.ChromaStore"), \
         patch("core.pipeline.KnowledgeBase"), \
         patch("core.pipeline.TranscriptionAgent"), \
         patch("core.pipeline.SpeakerAgent"), \
         patch("core.pipeline.AnalysisAgent"), \
         patch("core.pipeline.ReportAgent"), \
         patch("core.pipeline.AudioQualityChecker"):
        p = VoiceScopePipeline()

        quality = MagicMock()
        quality.should_proceed = True
        quality.model_dump.return_value = {"score": 0.9, "issues": []}
        p.audio_checker.check.return_value = quality

        async def fake_transcribe(ctx, audio_bytes, filename):
            ctx.raw_transcript = "Hello, I need help with my order."
            ctx.stages_completed.append("transcription")
            return ctx
        p.transcription_agent.run = fake_transcribe

        async def fake_analyze(ctx):
            ctx.intent = "support_request"
            ctx.sentiment_arc = "neutral"
            ctx.outcome = "resolved"
            ctx.hallucination_detected = False
            ctx.escalation_signal = False
            ctx.raw_analysis = {
                "intent": "support_request",
                "sentiment_arc": "neutral",
                "outcome": "resolved",
                "hallucination_detected": False,
                "escalation_signal": False,
            }
            ctx.stages_completed.append("analysis")
            return ctx
        p.analysis_agent.run = fake_analyze

        async def fake_report(ctx):
            ctx.report = {
                "intent": "support_request",
                "sentiment_arc": "neutral",
                "outcome": "resolved",
                "hallucination_detected": False,
                "escalation_signal": False,
                "quality_score": 85,
                "findings": [],
                "recommendations": [],
            }
            ctx.stages_completed.append("report")
            return ctx
        p.report_agent.run = fake_report

        yield p


async def test_pipeline_happy_path(pipeline):
    result = await pipeline.run(b"fake audio", "test.wav")

    assert "harness" in result
    assert result["harness"]["truth_score"] is not None
    assert result["harness"]["confidence"] in ("high", "medium", "low", "very_low")
    assert isinstance(result["errors"], list)
    assert "raw_transcript" in result
    assert result["raw_transcript"] == "Hello, I need help with my order."
    assert result["intent"] == "support_request"
    assert result["sentiment_arc"] == "neutral"


async def test_pipeline_transcription_failure():
    with patch("core.pipeline.ChromaStore"), \
         patch("core.pipeline.KnowledgeBase"), \
         patch("core.pipeline.TranscriptionAgent"), \
         patch("core.pipeline.SpeakerAgent"), \
         patch("core.pipeline.AnalysisAgent"), \
         patch("core.pipeline.ReportAgent"), \
         patch("core.pipeline.AudioQualityChecker"):
        p = VoiceScopePipeline()

        quality = MagicMock()
        quality.should_proceed = True
        quality.model_dump.return_value = {"score": 0.9, "issues": []}
        p.audio_checker.check.return_value = quality

        async def failing_transcribe(ctx, audio_bytes, filename):
            ctx.add_error("transcription", "STT service timed out")
            return ctx
        p.transcription_agent.run = failing_transcribe

        async def fake_report(ctx):
            ctx.report = {
                "quality_score": None,
                "findings": [],
                "recommendations": [],
            }
            return ctx
        p.report_agent.run = fake_report

        result = await p.run(b"fake audio", "test.wav")

        assert "harness" in result
        assert len(result["errors"]) > 0
        assert any("[transcription]" in e for e in result["errors"])


async def test_pipeline_analysis_failure(pipeline):
    async def failing_analyze(ctx):
        ctx.add_error("analysis", "LLM returned malformed JSON")
        return ctx
    pipeline.analysis_agent.run = failing_analyze

    async def fallback_report(ctx):
        ctx.report = {
            "quality_score": None,
            "findings": [],
            "recommendations": [],
        }
        return ctx
    pipeline.report_agent.run = fallback_report

    result = await pipeline.run(b"fake audio", "test.wav")

    assert "harness" in result
    assert len(result["errors"]) > 0
    assert any("[analysis]" in e for e in result["errors"])
