"""Exercise real attribution paths while isolating external providers and storage."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.sse import stream_analysis
from core.pipeline import VoiceScopePipeline
from llm_providers.base import CompletionResult
from llm_providers.registry import ProviderRegistry
from main import app
from storage.monitoring import MonitoringStore
from stt_providers.base import TranscriptionResult
from stt_providers.registry import STTRegistry


@pytest.fixture
def attributed_pipeline(monkeypatch, tmp_path):
    import core.pipeline
    import middleware.auth

    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'monitoring.db'))
    monkeypatch.setenv('COST_DB_PATH', str(tmp_path / 'costs.db'))
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'speaker-test-key'}))
    chroma = AsyncMock()
    chroma.query.return_value = []
    monkeypatch.setattr(core.pipeline, 'ChromaStore', lambda: chroma)
    monkeypatch.setattr(core.pipeline, 'KnowledgeBase', lambda: MagicMock(available=False))
    monkeypatch.setattr(ProviderRegistry, 'get', lambda *args, **kwargs: SimpleNamespace(name='test'))

    prompts = []

    async def complete(**kwargs):
        prompt = kwargs['prompt']
        prompts.append(prompt)
        if prompt.startswith('Identify conversational roles'):
            result = {'speaker_roles': {'0': 'customer', '1': 'agent'}}
        elif 'technical writer' in prompt:
            result = {
                'quality_score': 75,
                'executive_summary': 'A support conversation.',
                'key_findings': [],
                'recommendations': [],
            }
        else:
            result = {
                'intent': 'support request', 'sentiment_arc': 'neutral',
                'hallucination_detected': False, 'hallucination_evidence': None,
                'outcome': 'unresolved', 'escalation_signal': False, 'findings': [],
            }
        return CompletionResult(content=json.dumps(result), model='test-model', provider='test')

    model_call = AsyncMock(side_effect=complete)
    monkeypatch.setattr(ProviderRegistry, 'call', model_call)
    stt = SimpleNamespace(name='deepgram', transcribe=AsyncMock(return_value=TranscriptionResult(
        transcript='I need help. How can I assist?',
        speakers=[
            {'speaker': 0, 'text': 'I need help.'},
            {'speaker': 1, 'text': 'How can I assist?'},
        ],
        duration_seconds=10,
    )))
    monkeypatch.setattr(STTRegistry, 'get', lambda *args, **kwargs: stt)
    return SimpleNamespace(pipeline=VoiceScopePipeline(), stt=stt, prompts=prompts)


async def test_transcript_pipeline_keeps_caller_first_roles_without_retranscription(attributed_pipeline):
    transcript = 'user: I need help.\nassistant: How can I assist?\nuser: It remains unresolved.'
    result = await attributed_pipeline.pipeline.run_from_transcript(transcript)

    attributed_pipeline.stt.transcribe.assert_not_awaited()
    assert result['raw_transcript'] == transcript
    assert [turn['label'] for turn in result['transcript_speakers']] == ['Customer', 'Agent', 'Customer']
    assert all(turn['role_source'] == 'transcript_label' for turn in result['transcript_speakers'])
    assert result['attributed_transcript'].startswith('Customer: I need help.\nAgent:')
    assert not any(prompt.startswith('Identify conversational roles') for prompt in attributed_pipeline.prompts)
    assert any('Transcript:\nCustomer: I need help.\nAgent:' in prompt for prompt in attributed_pipeline.prompts)


async def test_audio_pipeline_attributes_real_diarization_before_analysis(attributed_pipeline):
    result = await attributed_pipeline.pipeline.run(b'\x01' * 64000, 'test.wav')

    attributed_pipeline.stt.transcribe.assert_awaited_once()
    assert result['raw_transcript'] == 'I need help. How can I assist?'
    assert [turn['role'] for turn in result['transcript_speakers']] == ['customer', 'agent']
    assert all(turn['role_source'] == 'model_inference' for turn in result['transcript_speakers'])
    assert 'Customer (inferred): I need help.' in result['attributed_transcript']
    assert any('Transcript:\nCustomer (inferred): I need help.' in prompt for prompt in attributed_pipeline.prompts)


async def test_streamed_audio_uses_same_attribution_and_persists_roles(attributed_pipeline):
    events = [json.loads(message[6:]) async for message in stream_analysis(b'\x01' * 64000, 'test.wav')]

    assert events[-1]['event'] == 'complete'
    result = events[-1]['result']
    assert [turn['role'] for turn in result['transcript_speakers']] == ['customer', 'agent']
    assert all(turn['role_source'] == 'model_inference' for turn in result['transcript_speakers'])
    assert any('Transcript:\nCustomer (inferred): I need help.' in prompt for prompt in attributed_pipeline.prompts)
    reloaded = await MonitoringStore().get_run(result['run_id'])
    assert reloaded['transcript_speakers'] == result['transcript_speakers']
    assert reloaded['evaluation']['attributed_transcript'] == result['attributed_transcript']


def test_bolna_webhook_preserves_labeled_transcript_and_source_after_reload(attributed_pipeline, monkeypatch):
    import api.routes

    monkeypatch.setattr(api.routes, 'get_pipeline', lambda: attributed_pipeline.pipeline)
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)
    download = MagicMock(side_effect=AssertionError('Labeled Bolna transcript must not trigger audio download'))
    monkeypatch.setattr(api.routes.httpx, 'AsyncClient', download)
    transcript = 'user: I need help.\nassistant: How can I assist?\nuser: It remains unresolved.'
    payload = {
        'id': '11111111-1111-4111-8111-111111111111',
        'agent_id': '22222222-2222-4222-8222-222222222222',
        'status': 'completed', 'conversation_duration': 10,
        'transcript': transcript, 'telephony_data': {},
    }
    headers = {'X-API-Key': 'speaker-test-key'}
    with TestClient(app) as client:
        response = client.post('/api/v1/webhooks/call-completed', json=payload, headers=headers)
        assert response.status_code == 200
        result = response.json()['pipeline_result']
        loaded_response = client.get(f"/api/v1/runs/{result['run_id']}", headers=headers)

    assert loaded_response.status_code == 200
    attributed_pipeline.stt.transcribe.assert_not_awaited()
    download.assert_not_called()
    assert result['transcript_source'] == 'bolna'
    assert result['raw_transcript'] == transcript
    assert result['transcript_meta']['duration_seconds'] == 10
    assert [turn['role'] for turn in result['transcript_speakers']] == ['customer', 'agent', 'customer']
    loaded = loaded_response.json()
    assert loaded['transcript_speakers'] == result['transcript_speakers']
    assert loaded['evaluation']['raw_transcript'] == transcript
    assert loaded['evaluation']['source_call']['call_id'] == payload['id']
    assert loaded['evaluation']['source_call']['agent_id'] == payload['agent_id']
