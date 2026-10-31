import io
from unittest.mock import AsyncMock, patch

import pytest

from core.context import PipelineContext
from utils.logger import logger, private_log_record

CANARY = 'synthetic-caller-address-and-signed-recording-token'


def test_exception_logs_omit_provider_messages_and_traceback_values():
    output = io.StringIO()
    sink = logger.add(output, filter=private_log_record, format='{message} {extra}', diagnose=False, backtrace=False)
    try:
        try:
            raise RuntimeError(CANARY)
        except RuntimeError:
            logger.exception('Synthetic provider failed')
    finally:
        logger.remove(sink)
    assert CANARY not in output.getvalue()
    assert 'RuntimeError' in output.getvalue()


async def test_transcription_failure_never_persists_or_logs_provider_payload():
    from agents.transcription_agent import TranscriptionAgent
    provider = AsyncMock(name='provider')
    provider.name = 'deepgram'
    provider.transcribe.side_effect = RuntimeError(CANARY)
    output = io.StringIO()
    sink = logger.add(output, filter=private_log_record, diagnose=False, backtrace=False)
    try:
        with patch('agents.transcription_agent.STTRegistry.get', return_value=provider):
            context = await TranscriptionAgent().run(PipelineContext(), b'synthetic audio', CANARY + '.wav')
    finally:
        logger.remove(sink)
    assert context.errors
    assert CANARY not in str(context.model_dump())
    assert CANARY not in output.getvalue()


async def test_report_failure_does_not_return_provider_response_text():
    from agents.report_agent import ReportAgent
    with patch('agents.report_agent.ProviderRegistry.get', return_value=AsyncMock()):
        agent = ReportAgent(chroma_store=AsyncMock())
    with patch('agents.report_agent.ProviderRegistry.call', new_callable=AsyncMock, side_effect=RuntimeError(CANARY)) as call:
        context = await agent.run(PipelineContext())
        call.assert_awaited_once()
    assert context.errors
    assert context.report['quality_score'] is None
    assert CANARY not in str(context.model_dump())


@pytest.mark.parametrize('query', [CANARY, 'normal synthetic query'])
async def test_knowledge_query_logs_only_counts(query):
    from core.knowledge_base import KnowledgeBase
    from unittest.mock import MagicMock
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb.available = True
    kb.collection = MagicMock()
    kb.collection.query.return_value = {'documents': [['Synthetic policy']]}
    output = io.StringIO()
    sink = logger.add(output, level='DEBUG', filter=private_log_record)
    try:
        assert await kb.query(query) == ['Synthetic policy']
    finally:
        logger.remove(sink)
    assert query not in output.getvalue()


async def test_database_startup_error_does_not_log_raw_exception(monkeypatch):
    import main
    monkeypatch.setenv('DATABASE_URL', 'synthetic-configured-url')
    monkeypatch.setattr(main, 'init_schema', AsyncMock(side_effect=RuntimeError(CANARY)))
    monkeypatch.setattr(main, 'close_pool', AsyncMock())
    output = io.StringIO()
    sink = logger.add(output, filter=private_log_record, format='{message}', diagnose=False, backtrace=False)
    try:
        async with main.lifespan(main.app):
            pass
    finally:
        logger.remove(sink)
    assert CANARY not in output.getvalue()
    assert 'RuntimeError' in output.getvalue()
