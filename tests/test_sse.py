import json
import os

import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

from unittest.mock import AsyncMock, MagicMock, patch

from api.sse import stream_analysis
from core.context import PipelineContext
from core.pipeline import VoiceScopePipeline
from core.harness import HarnessResult


@pytest.mark.asyncio
async def test_sse_started_event():
    mock_pipeline = MagicMock()
    mock_pipeline.attribute_speakers = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.assess_reliability = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.finalize_result.side_effect = lambda ctx, result: VoiceScopePipeline.finalize_result(mock_pipeline, ctx, result)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription", "analysis", "report"]

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
    mock_pipeline.attribute_speakers = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.assess_reliability = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.finalize_result.side_effect = lambda ctx, result: VoiceScopePipeline.finalize_result(mock_pipeline, ctx, result)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription", "analysis", "report"]
    mock_ctx.report = {"quality_score": 85}

    mock_pipeline.transcription_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.analysis_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.report_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult(truth_score=0.8, confidence="high")

    with patch("api.sse.VoiceScopePipeline", return_value=mock_pipeline):
        events = []
        async for line in stream_analysis(b"audio", "test.mp3"):
            if line.startswith("data: "):
                data = json.loads(line[6:].strip())
                events.append(data)

    assert events[-1]["event"] == "complete"
    assert events[-1]["result"]["quality_score"] == 85
    assert events[-1]["result"]["harness"]["truth_score"] == 0.8


@pytest.mark.asyncio
async def test_sse_stage_events():
    mock_pipeline = MagicMock()
    mock_pipeline.attribute_speakers = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.assess_reliability = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.finalize_result.side_effect = lambda ctx, result: VoiceScopePipeline.finalize_result(mock_pipeline, ctx, result)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult()
    mock_ctx = PipelineContext()
    mock_ctx.raw_transcript = "test transcript"
    mock_ctx.stages_completed = ["transcription", "analysis", "report"]

    mock_pipeline.transcription_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.analysis_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.report_agent.run = AsyncMock(return_value=mock_ctx)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult(truth_score=0.8)

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
    assert "harness" in stages


@pytest.mark.asyncio
async def test_sse_error_event():
    mock_pipeline = MagicMock()
    mock_pipeline.attribute_speakers = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.assess_reliability = AsyncMock(side_effect=lambda ctx: ctx)
    mock_pipeline.finalize_result.side_effect = lambda ctx, result: VoiceScopePipeline.finalize_result(mock_pipeline, ctx, result)
    mock_pipeline.harness.validate_pipeline.return_value = HarnessResult()
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


async def test_sse_failure_does_not_report_skipped_stages_complete(tmp_path, monkeypatch):
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'monitoring.db'))
    monkeypatch.setenv('COST_DB_PATH', str(tmp_path / 'cost.db'))
    pipeline = MagicMock()
    ctx = PipelineContext()
    ctx.add_error('transcription', 'STT failed')
    pipeline.transcription_agent.run = AsyncMock(return_value=ctx)
    pipeline.harness.validate_pipeline.return_value = HarnessResult(validation_passed=False)
    pipeline.finalize_result.side_effect = lambda context, result: VoiceScopePipeline.finalize_result(pipeline, context, result)
    with patch('api.sse.VoiceScopePipeline', return_value=pipeline):
        events = [json.loads(line[6:]) async for line in stream_analysis(b'audio', 'test.wav')]
    pipeline.report_agent.run.assert_not_called()
    pipeline.analysis_agent.run.assert_not_called()
    assert events[-1]['result']['status'] == 'failed'
    assert not any(event.get('stage') in {'transcription', 'analysis', 'report'} for event in events)


async def test_pipeline_startup_failure_is_a_terminal_stream_error():
    with patch('api.sse.VoiceScopePipeline', side_effect=RuntimeError('private startup configuration')):
        events = [json.loads(line[6:]) async for line in stream_analysis(b'audio', 'test.wav')]
    assert [event['event'] for event in events] == ['started', 'error']
    assert events[-1]['detail'] == 'Analysis failed'
    assert 'private startup' not in json.dumps(events)
