import os
import json
import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

from unittest.mock import AsyncMock, MagicMock, patch
from api.sse import stream_analysis
from core.context import PipelineContext


@pytest.mark.asyncio
async def test_sse_started_event():
    mock_pipeline = MagicMock()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription"]

    mock_pipeline.transcription_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.analysis_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.report_agent.run = AsyncMock(return_value=mock_ctx)

    with patch("api.sse.VoiceScopePipeline", return_value=mock_pipeline):
        events = []
        async for line in stream_analysis(b"audio", "test.mp3"):
            if line.startswith("data: "):
                data = json.loads(line[6:].strip())
                events.append(data)

    assert events[0]["event"] == "started"
    assert "run_id" in events[0]


@pytest.mark.asyncio
async def test_sse_complete_event():
    mock_pipeline = MagicMock()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription"]
    mock_ctx.report = {"quality_score": 85}

    mock_pipeline.transcription_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.analysis_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.report_agent.run = AsyncMock(return_value=mock_ctx)

    with patch("api.sse.VoiceScopePipeline", return_value=mock_pipeline):
        events = []
        async for line in stream_analysis(b"audio", "test.mp3"):
            if line.startswith("data: "):
                data = json.loads(line[6:].strip())
                events.append(data)

    assert events[-1]["event"] == "complete"
    assert events[-1]["result"]["quality_score"] == 85


@pytest.mark.asyncio
async def test_sse_stage_events():
    mock_pipeline = MagicMock()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription"]

    mock_pipeline.transcription_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.analysis_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.report_agent.run = AsyncMock(return_value=mock_ctx)

    with patch("api.sse.VoiceScopePipeline", return_value=mock_pipeline):
        events = []
        async for line in stream_analysis(b"audio", "test.mp3"):
            if line.startswith("data: "):
                data = json.loads(line[6:].strip())
                events.append(data)

    stage_events = [e for e in events if e["event"] == "stage_complete"]
    stages = [e["stage"] for e in stage_events]
    assert "transcription" in stages
    assert "report" in stages


@pytest.mark.asyncio
async def test_sse_error_event():
    mock_pipeline = MagicMock()
    mock_pipeline.transcription_agent.run = AsyncMock(side_effect=Exception("boom"))

    with patch("api.sse.VoiceScopePipeline", return_value=mock_pipeline):
        events = []
        async for line in stream_analysis(b"audio", "test.mp3"):
            if line.startswith("data: "):
                data = json.loads(line[6:].strip())
                events.append(data)

    assert events[0]["event"] == "started"
    assert events[-1]["event"] == "error"
    assert events[-1]["detail"] == "Analysis failed"
