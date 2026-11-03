"""Only the explicitly authorized QA agent may enter the public test deployment."""

import hashlib
import io
import wave
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

AGENT = '11111111-1111-4111-8111-111111111111'
CALL = '22222222-2222-4222-8222-222222222222'
KEY = 'isolated-test-api-key-with-32-characters'
SECRET = 'separate-test-webhook-secret-32-characters'


@pytest.fixture
def qa(monkeypatch, tmp_path):
    import middleware.auth
    import api.routes

    for name in ['DATABASE_URL', 'BOLNA_API_KEY', 'DEEPGRAM_API_KEY', 'STAGING_QA_DEEPGRAM', 'GROQ_API_KEY',
                 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'MISTRAL_API_KEY',
                 'OPENROUTER_API_KEY', 'OPENCODE_GO_API_KEY', 'MONITORING_DB_PATH',
                 'POLICY_DB_PATH', 'STT_REVIEW_DIR', 'CHROMA_PERSIST_DIR', 'COST_DB_PATH',
                 'KNOWLEDGE_DB_PATH', 'QA_DB_PATH', 'EXTRACTIONS_DB_PATH', 'OPTIMIZER_DB_PATH']:
        monkeypatch.delenv(name, raising=False)
    for name, value in {'STAGING_DEMO_ONLY': 'true', 'PUBLIC_SYNTHETIC_DEMO': 'true',
                        'STAGING_QA_AGENT_ID': AGENT, 'VALID_API_KEYS': KEY,
                        'BOLNA_WEBHOOK_SECRET': SECRET, 'DATA_DIR': str(tmp_path)}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({KEY}))
    monkeypatch.setattr(middleware.auth, '_WEBHOOK_KEY', SECRET)
    api.routes.get_monitoring_store.cache_clear()
    monkeypatch.setattr(api.routes, 'get_pipeline', lambda: pytest.fail('Paid pipeline called'))
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b'\0' * 32000)
    from core import staging_qa
    download = AsyncMock(return_value=(audio.getvalue(), 'audio/wav'))
    monkeypatch.setattr(staging_qa, 'retrieve_qa_recording', download)
    yield TestClient(__import__('main').app), download
    api.routes.get_monitoring_store.cache_clear()


def payload(**changes):
    return {'id': CALL, 'agent_id': AGENT, 'status': 'completed',
            'transcript': 'user: Hello.\nassistant: How can I help?',
            'conversation_duration': 1, 'telephony_data': {}, **changes}


def test_authenticated_replay_preserves_transcript_audio_and_not_scored(qa):
    client, download = qa
    headers = {'X-Webhook-Key': SECRET}
    response = client.post('/api/v1/webhooks/call-completed', headers=headers, json=payload())
    assert response.status_code == 200, response.text
    assert 'pipeline_result' not in response.json()
    run = client.get('/api/v1/runs/' + CALL, headers={'X-API-Key': KEY}).json()
    result = run['evaluation']
    assert result['raw_transcript'] == payload()['transcript']
    assert result['data_source'] == 'authorized_live_qa'
    assert result['stt_quality']['metric_value'] is None
    assert result['stt_quality']['status'] == 'blocked'
    assert result['source_call']['agent_id'] == AGENT
    assert result['report']['quality_score'] is None
    assert 'provider' not in result
    audio = client.get(f'/api/v1/runs/{CALL}/stt-review/audio',
                       headers={'X-API-Key': KEY, 'Range': 'bytes=0-99'})
    assert audio.status_code == 206
    assert len(audio.content) == 100
    assert audio.headers['cache-control'] == 'no-store'
    assert client.post('/api/v1/webhooks/call-completed', headers=headers, json=payload()).status_code == 200
    assert download.await_count == 1


@pytest.mark.parametrize('changes', [{'agent_id': 'another-agent'}, {'transcript': ''}, {'id': 'not-a-uuid'}])
def test_rejects_wrong_agent_or_unusable_evidence(qa, changes):
    client, download = qa
    response = client.post('/api/v1/webhooks/call-completed', headers={'X-Webhook-Key': SECRET}, json=payload(**changes))
    assert response.status_code in (403, 422)
    download.assert_not_awaited()


@pytest.mark.parametrize('headers', [{}, {'X-Webhook-Key': 'invalid'}, {'X-API-Key': KEY},
                                   {'X-API-Key': KEY, 'X-Webhook-Key': 'invalid'}])
def test_webhook_requires_separate_webhook_secret(qa, headers):
    client, download = qa
    assert client.post('/api/v1/webhooks/call-completed', headers=headers, json=payload()).status_code in (401, 403)
    download.assert_not_awaited()


@pytest.mark.parametrize('method,path', [('post', '/api/v1/analyze'), ('post', '/api/v1/policies/rules'),
    ('delete', '/api/v1/runs/' + CALL), ('post', f'/api/v1/runs/{CALL}/stt-review/reference')])
def test_public_mutations_stay_blocked(qa, method, path):
    client, _ = qa
    assert getattr(client, method)(path, headers={'X-API-Key': KEY}).status_code == 403


def test_failed_recording_is_retryable_and_never_acknowledged_as_success(qa):
    client, download = qa
    download.side_effect = ValueError('private signed URL must not escape')
    response = client.post('/api/v1/webhooks/call-completed', headers={'X-Webhook-Key': SECRET}, json=payload())
    assert response.status_code == 503
    assert 'private signed' not in response.text
    download.side_effect = None
    assert client.post('/api/v1/webhooks/call-completed', headers={'X-Webhook-Key': SECRET}, json=payload()).status_code == 200


async def test_restart_accepts_only_authorized_qa_provenance(qa, monkeypatch):
    from core.staging_demo import seed_staging_demo
    from storage.monitoring import MonitoringStore
    from storage.stt_reviews import STTReviewStore

    client, _ = qa
    await seed_staging_demo()
    assert client.post('/api/v1/webhooks/call-completed', headers={'X-Webhook-Key': SECRET}, json=payload()).status_code == 200
    await seed_staging_demo()
    assert (await MonitoringStore().get_runs())['total'] == 7
    assert STTReviewStore().read(hashlib.sha256(KEY.encode()).hexdigest(), CALL)
    monkeypatch.setenv('STAGING_QA_AGENT_ID', '33333333-3333-4333-8333-333333333333')
    with pytest.raises(ValueError, match='non-synthetic'):
        await seed_staging_demo()


async def test_qa_recording_uses_only_stable_bolna_url(qa, monkeypatch):
    from core import stt_recording
    monkeypatch.setenv('BOLNA_API_KEY', 'test-only-bolna-key')
    download = AsyncMock(return_value=(b'audio', 'audio/wav'))
    monkeypatch.setattr(stt_recording, '_download_recording', download)
    assert await stt_recording.retrieve_qa_recording(CALL) == (b'audio', 'audio/wav')
    download.assert_awaited_once_with('https://api.bolna.ai/recordings/call/' + CALL,
                                      {'Authorization': 'Bearer test-only-bolna-key'})
    with pytest.raises(ValueError):
        await stt_recording.retrieve_qa_recording('https://private.invalid/')
    assert download.await_count == 1
    monkeypatch.delenv('STAGING_QA_AGENT_ID')
    with pytest.raises(ValueError, match='not enabled'):
        await stt_recording.retrieve_qa_recording(CALL)
    assert download.await_count == 1


def test_qa_mode_never_permits_ai_provider_keys_or_shared_webhook_key(qa, monkeypatch):
    from core.staging import validate_demo_environment
    monkeypatch.setenv('BOLNA_API_KEY', 'test-only-recording-retrieval')
    assert validate_demo_environment() == [KEY]
    monkeypatch.setenv('OPENAI_API_KEY', 'must-remain-forbidden')
    with pytest.raises(ValueError, match='live provider'):
        validate_demo_environment()
    monkeypatch.delenv('OPENAI_API_KEY')
    monkeypatch.setenv('BOLNA_WEBHOOK_SECRET', KEY)
    with pytest.raises(ValueError, match='separate'):
        validate_demo_environment()


@pytest.mark.parametrize('failure', [False, True])
def test_opted_in_qa_reference_runs_once_and_never_invents_a_score(qa, monkeypatch, failure):
    from stt_providers.registry import STTRegistry
    from stt_providers.base import TranscriptionResult
    monkeypatch.setenv('STAGING_QA_DEEPGRAM', 'true')
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'test-only-deepgram-key')
    provider = AsyncMock()
    provider.transcribe.return_value = TranscriptionResult(transcript='Hello', words=[
        {'word': 'Hello', 'speaker': 0, 'start': 0.1, 'end': 0.3}])
    if failure:
        provider.transcribe.side_effect = RuntimeError('secret provider response must stay private')
    monkeypatch.setattr(STTRegistry, '_instances', {'deepgram': provider})
    client, _ = qa
    for _ in range(2):
        assert client.post('/api/v1/webhooks/call-completed', headers={'X-Webhook-Key': SECRET}, json=payload()).status_code == 200
    provider.transcribe.assert_awaited_once()
    state = client.get(f'/api/v1/runs/{CALL}/stt-review', headers={'X-API-Key': KEY}).json()
    assert state['provider']['configured'] is True
    assert state['review']['metric_value'] is None
    assert state['review']['status'] == ('failed' if failure else 'blocked')
    assert bool(state['reference']) is not failure
    assert 'secret provider' not in str(state)
    assert client.post(f'/api/v1/runs/{CALL}/stt-review/reference', headers={'X-API-Key': KEY}, json={}).status_code == 403
    if not failure:
        cached = client.post(f'/api/v1/runs/{CALL}/stt-review/reference', headers={'X-API-Key': KEY, 'X-Webhook-Key': SECRET}, json={})
        assert cached.status_code == 200
        provider.transcribe.assert_awaited_once()


async def test_deepgram_opt_in_does_not_enable_other_providers(qa, monkeypatch):
    from core.staging import validate_demo_environment
    from stt_providers.registry import STTRegistry
    from llm_providers.registry import ProviderRegistry
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'test-key')
    with pytest.raises(ValueError):
        validate_demo_environment()
    monkeypatch.setenv('STAGING_QA_DEEPGRAM', 'true')
    assert validate_demo_environment() == [KEY]
    monkeypatch.delenv('DEEPGRAM_API_KEY')
    with pytest.raises(ValueError, match='credentials'):
        validate_demo_environment()
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'test-key')
    assert STTRegistry.get('deepgram').name == 'deepgram'
    with pytest.raises(RuntimeError, match='demo'):
        STTRegistry.get('whisper')
    monkeypatch.setenv('OPENAI_API_KEY', 'must-stay-forbidden')
    with pytest.raises(ValueError):
        validate_demo_environment()
    with pytest.raises(RuntimeError, match='demo'):
        from core.staging import require_live_services
        require_live_services()
    with pytest.raises(RuntimeError, match='demo'):
        await ProviderRegistry.call('openai', prompt='Must not run')


def test_operator_can_restore_cached_reference_without_triggering_paid_calls(qa, monkeypatch):
    from storage.stt_reviews import STTReviewStore
    from stt_providers.registry import STTRegistry
    from core.stt_quality import Transcript, Segment
    monkeypatch.setenv('STAGING_QA_DEEPGRAM', 'true')
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'test-only-deepgram')
    provider = AsyncMock()
    monkeypatch.setattr(STTRegistry, '_instances', {'deepgram': provider})
    client, _ = qa
    headers = {'X-API-Key': KEY, 'X-Webhook-Key': SECRET, 'X-STT-Reference-Mode': 'restore'}
    assert client.post('/api/v1/webhooks/call-completed', headers=headers, json=payload()).status_code == 200
    provider.transcribe.assert_not_awaited()
    artifact = STTReviewStore().read(hashlib.sha256(KEY.encode()).hexdigest(), CALL)
    reference = Transcript(source='deepgram', audio_sha256=artifact['audio_info']['sha256'],
                           segments=[Segment(text='Hello', speaker='dg_0', start=.1, end=.5)])
    body = {'saved_reference': reference.model_dump()}
    assert client.post(f'/api/v1/runs/{CALL}/stt-review/reference', headers={'X-API-Key': KEY}, json=body).status_code == 403
    response = client.post(f'/api/v1/runs/{CALL}/stt-review/reference', headers=headers, json=body)
    assert response.status_code == 200
    assert response.json()['reference']['audio_sha256'] == artifact['audio_info']['sha256']
    assert response.json()['review']['metric_value'] is None
    provider.transcribe.assert_not_awaited()
    body['saved_reference']['audio_sha256'] = 'b' * 64
    assert client.post(f'/api/v1/runs/{CALL}/stt-review/reference', headers=headers, json=body).status_code == 422
