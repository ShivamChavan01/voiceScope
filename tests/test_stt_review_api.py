import copy
import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from core.stt_quality import Segment
from core.stt_sources import bolna_transcript
from main import app
from storage.stt_reviews import STTReviewStore
from stt_providers.base import TranscriptionResult

HEADERS = {'X-API-Key': 'stt-test', 'X-STT-Review': '1'}
OWNER = hashlib.sha256(b'stt-test').hexdigest()
AUDIO = b'synthetic original recording'
HASH = hashlib.sha256(AUDIO).hexdigest()
RUN = {'run_id': 'run-stt', 'status': 'completed', 'evaluation': {'transcript_source': 'bolna',
    'source_call': {'platform': 'bolna', 'call_id': '00000000-0000-0000-0000-000000000001'},
    'raw_transcript': 'user: I do want a refund', 'report': {'executive_summary': 'Existing report'}}}


@pytest.fixture(autouse=True)
def private_store(monkeypatch, tmp_path):
    import middleware.auth
    monkeypatch.setenv('STT_REVIEW_DIR', str(tmp_path / 'private'))
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'fake-test-key')
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'stt-test', 'other-key'}))
    store = AsyncMock()
    store.get_run.side_effect = lambda run_id: copy.deepcopy(RUN) if run_id == RUN['run_id'] else None
    monkeypatch.setattr('api.routes.get_monitoring_store', lambda: store)


def seed_recording():
    STTReviewStore().save(OWNER, RUN['run_id'], audio=AUDIO, content_type='audio/wav',
        audio_info={'available': True, 'sha256': HASH, 'duration_seconds': 10, 'scope': 'unknown'})


def test_reference_preparation_does_not_upload_audio_without_recording_hash():
    STTReviewStore().save(OWNER, RUN['run_id'], audio=AUDIO, content_type='audio/wav',
        audio_info={'available': True, 'duration_seconds': 10, 'scope': 'unknown'})
    provider = AsyncMock()
    with patch('core.stt_service.STTRegistry.get', return_value=provider):
        response = TestClient(app).post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={})
    assert response.status_code == 200
    assert response.json()['review']['status'] == 'failed'
    assert response.json()['review']['metric_value'] is None
    assert response.json()['reference'] is None
    provider.transcribe.assert_not_awaited()


def human_body():
    original = bolna_transcript(RUN['evaluation']['raw_transcript'])
    original.segments[0].start, original.segments[0].end = 0, 3
    return {'recording_scope': 'caller_only', 'scope_confirmed': True, 'bolna_annotations': original.model_dump(),
        'human_reference': {'source': 'human', 'scope': 'caller_only', 'audio_sha256': HASH,
            'human_verified': True, 'verified_by': 'Synthetic test reviewer',
            'segments': [Segment(text='I do not want a refund', speaker='caller', role='caller', start=0, end=3).model_dump()]}}


def test_missing_recording_and_reference_do_not_produce_scores():
    client = TestClient(app)
    response = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json={})
    assert response.status_code == 200
    assert response.json()['review']['metric_value'] is None
    assert response.json()['review']['status'] == 'blocked'
    assert client.get('/api/v1/runs/run-stt/stt-review/audio', headers=HEADERS).status_code == 404


def test_human_wer_evidence_and_report_survive_reload_and_are_owner_scoped():
    seed_recording()
    client = TestClient(app)
    response = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body())
    assert response.status_code == 200
    review = response.json()['review']
    assert review['metric_kind'] == 'wer'
    assert review['metric_value'] == 1 / 6
    assert review['findings'][0]['category'] == ['negation']
    assert review['findings'][0]['start'] == 0
    assert review['findings'][0]['status'] == 'confirmed_error'
    assert review['verified_by'] == 'Synthetic test reviewer'
    assert client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()['review'] == review
    run = client.get('/api/v1/runs/run-stt', headers=HEADERS).json()
    assert run['evaluation']['report']['executive_summary'] == 'Existing report'
    assert run['evaluation']['report']['stt_quality']['evidence'] == review['findings']
    other = {'X-API-Key': 'other-key'}
    assert client.get('/api/v1/runs/run-stt/stt-review', headers=other).json()['review'] is None
    assert 'stt_quality' not in client.get('/api/v1/runs/run-stt', headers=other).json()['evaluation']
    assert client.get('/api/v1/runs/run-stt/stt-review/audio', headers=other).status_code == 404
    audio = client.get('/api/v1/runs/run-stt/stt-review/audio', headers=HEADERS)
    assert audio.content == AUDIO
    assert audio.headers['cache-control'] == 'no-store'


def test_reference_generation_honors_explicit_opt_out_and_restricts_provider():
    client = TestClient(app)
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock) as retrieve:
        response = client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'deepgram', 'consent_to_deepgram': False})
        assert response.status_code == 422
        retrieve.assert_not_awaited()
    assert client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'new-provider', 'consent_to_deepgram': True}).status_code == 422


def test_automatic_pass_is_cached_and_missing_bolna_timing_stays_partial():
    seed_recording()
    result = TranscriptionResult(transcript='I do not want a refund', words=[{'word': text, 'speaker': 0, 'start': index / 2, 'end': index / 2 + 0.4} for index, text in enumerate('I do not want a refund'.split())])
    provider = AsyncMock()
    provider.transcribe.return_value = result
    client = TestClient(app)
    with patch('core.stt_service.STTRegistry.get', return_value=provider):
        for _ in range(2):
            response = client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'deepgram', 'consent_to_deepgram': True})
            assert response.status_code == 200
        provider.transcribe.assert_awaited_once()
    response = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json={
        'recording_scope': 'caller_only', 'scope_confirmed': True,
        'speaker_roles': {'dg_0': 'caller'}, 'speaker_mapping_confirmed': True})
    assert response.json()['review']['status'] == 'partial'
    assert response.json()['review']['metric_value'] is None
    assert response.json()['review']['findings'][0]['status'] == 'needs_review'


def test_provider_outage_has_sanitized_failure_and_no_score():
    seed_recording()
    provider = AsyncMock()
    provider.transcribe.side_effect = RuntimeError('secret token and private transcript')
    with patch('core.stt_service.STTRegistry.get', return_value=provider):
        response = TestClient(app).post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'deepgram', 'consent_to_deepgram': True})
    assert response.json()['review']['status'] == 'failed'
    assert response.json()['review']['metric_value'] is None
    assert 'secret token' not in response.text


def test_invalid_hash_annotation_and_unverified_human_source_rejected():
    seed_recording()
    body = human_body()
    body['human_reference']['audio_sha256'] = 'b' * 64
    client = TestClient(app)
    response = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=body)
    assert response.json()['review']['status'] == 'blocked'
    assert response.json()['review']['metric_value'] is None
    body = human_body()
    body['bolna_annotations']['segments'][0]['text'] = 'Rewritten words'
    assert client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=body).status_code == 422
    body = human_body()
    body['human_reference']['human_verified'] = False
    assert client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=body).status_code == 422


def test_auth_and_missing_run_are_enforced():
    client = TestClient(app)
    assert client.get('/api/v1/runs/run-stt/stt-review').status_code == 401
    assert client.get('/api/v1/runs/missing/stt-review', headers=HEADERS).status_code == 404


def test_webhook_preserves_original_bolna_transcript_without_sending_audio(monkeypatch, tmp_path):
    from storage.monitoring import MonitoringStore
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'webhook-runs.db'))
    monkeypatch.setattr('api.routes.get_monitoring_store', MonitoringStore)
    pipeline = AsyncMock()
    pipeline.run_from_transcript.return_value = {'run_id': 'webhook-stt', 'analysis': {}, 'report': {}}
    monkeypatch.setattr('api.routes.get_pipeline', lambda: pipeline)
    with patch('api.routes._log_cost', new_callable=AsyncMock), patch('api.routes._log_metrics', new_callable=AsyncMock):
        response = TestClient(app).post('/api/v1/webhooks/call-completed', headers=HEADERS, json={'id': 'call', 'agent_id': 'agent', 'status': 'completed', 'transcript': 'user: Original words', 'telephony_data': {}, 'conversation_duration': 5})
        assert response.status_code == 200
        loaded = TestClient(app).get('/api/v1/runs/webhook-stt', headers=HEADERS)
        assert loaded.status_code == 200
        source = loaded.json()['evaluation']['stt_source']
        assert source['segments'][0]['text'] == 'Original words'
        assert source['segments'][0]['start'] is None
        pipeline.run.assert_not_awaited()


def test_aligned_auto_reference_reports_disagreement_and_never_wer():
    seed_recording()
    STTReviewStore().save(OWNER, RUN['run_id'], reference={'source': 'deepgram', 'scope': 'unknown', 'audio_sha256': HASH,
        'segments': [Segment(text='I do not want a refund', speaker='dg_0', start=0, end=3).model_dump()]})
    original = human_body()['bolna_annotations']
    response = TestClient(app).post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json={
        'recording_scope': 'caller_only', 'scope_confirmed': True, 'bolna_annotations': original,
        'speaker_roles': {'dg_0': 'caller'}, 'speaker_mapping_confirmed': True})
    assert response.status_code == 200
    assert response.json()['review']['metric_kind'] == 'estimated_disagreement'
    assert response.json()['review']['reference_human_verified'] is False
    assert response.json()['review']['findings'][0]['status'] == 'needs_review'


def test_missing_transcript_and_recording_fail_without_fabricated_scores(monkeypatch):
    monkeypatch.setattr('core.stt_service.original_transcript', lambda run: bolna_transcript(''))
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock) as retrieve:
        result = TestClient(app).post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'deepgram', 'consent_to_deepgram': True})
        assert result.json()['review']['status'] == 'blocked'
        retrieve.assert_not_awaited()


def test_failed_download_has_no_provider_call_or_score():
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock, side_effect=ValueError('private URL')) as retrieve, patch('core.stt_service.STTRegistry.get') as provider:
        result = TestClient(app).post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={'provider': 'deepgram', 'consent_to_deepgram': True})
        assert result.json()['review']['status'] == 'failed'
        assert 'private URL' not in result.text
        retrieve.assert_awaited_once()
        provider.assert_not_called()


def test_recording_only_retrieval_is_cached_without_invoking_stt():
    client = TestClient(app)
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock, return_value=(AUDIO, 'audio/wav')) as retrieve, patch('core.stt_service.STTRegistry.get') as provider:
        for _ in range(2):
            result = client.post('/api/v1/runs/run-stt/stt-review/recording', headers=HEADERS)
            assert result.status_code == 200
            assert result.json()['audio']['sha256'] == HASH
            assert result.json()['reference'] is None
        retrieve.assert_awaited_once()
        provider.assert_not_called()


def test_recording_failure_is_sanitized_and_shared_proxy_cannot_read_report():
    client = TestClient(app)
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock, side_effect=RuntimeError('private recording URL')):
        result = client.post('/api/v1/runs/run-stt/stt-review/recording', headers=HEADERS)
        assert result.json()['review']['status'] == 'failed'
        assert 'private recording URL' not in result.text
    run = client.get('/api/v1/runs/run-stt', headers={'X-API-Key': 'stt-test'}).json()
    assert 'stt_quality' not in run['evaluation']


def test_recording_retry_clears_stale_download_failure_and_missing_source_blocks(monkeypatch):
    client = TestClient(app)
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock, side_effect=[RuntimeError('offline'), (AUDIO, 'audio/wav')]):
        assert client.post('/api/v1/runs/run-stt/stt-review/recording', headers=HEADERS).json()['review']['status'] == 'failed'
        result = client.post('/api/v1/runs/run-stt/stt-review/recording', headers=HEADERS).json()
        assert result['audio']['available'] is True
        assert result['review']['status'] == 'blocked'
        assert 'failed' not in result['review']['issues'][0]
    STTReviewStore().delete_run(RUN['run_id'])
    store = AsyncMock()
    store.get_run.return_value = {'run_id': 'run-stt', 'evaluation': {}}
    monkeypatch.setattr('api.routes.get_monitoring_store', lambda: store)
    with patch('core.stt_service.retrieve_bolna_recording', new_callable=AsyncMock) as retrieve:
        result = client.post('/api/v1/runs/run-stt/stt-review/recording', headers=HEADERS).json()
        assert result['review']['status'] == 'blocked'
        retrieve.assert_not_awaited()


def test_reference_action_uses_authorized_deepgram_without_repeated_consent():
    seed_recording()
    provider = AsyncMock()
    provider.transcribe.return_value = TranscriptionResult(transcript='hello', words=[{'word': 'hello', 'speaker': 0, 'start': 0, 'end': 1}])
    client = TestClient(app)
    with patch('core.stt_service.STTRegistry.get', return_value=provider):
        state = client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()
        assert state['provider']['requires_consent'] is False
        provider.transcribe.assert_not_awaited()
        response = client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={})
        assert response.status_code == 200
        assert response.json()['reference']['source'] == 'deepgram'
        provider.transcribe.assert_awaited_once()


@pytest.mark.parametrize('outage', [False, True])
async def test_concurrent_reference_requests_share_one_provider_submission(outage):
    import asyncio
    from core.stt_service import create_reference
    seed_recording()
    provider = AsyncMock()

    async def transcribe(*args):
        await asyncio.sleep(0.01)
        if outage:
            raise RuntimeError('provider unavailable')
        return TranscriptionResult(transcript='hello', words=[{'word': 'hello', 'speaker': 0, 'start': 0, 'end': 1}])

    provider.transcribe.side_effect = transcribe
    with patch('core.stt_service.STTRegistry.get', return_value=provider):
        results = await asyncio.gather(*(create_reference(RUN, OWNER, STTReviewStore()) for _ in range(5)))
    provider.transcribe.assert_awaited_once()
    assert all(result['reference'] == results[0]['reference'] for result in results)
    if outage:
        assert all(result['review']['status'] == 'failed' for result in results)


def test_automatic_reference_never_overwrites_human_review_or_needs_provider_key_for_cached_result(monkeypatch):
    seed_recording()
    client = TestClient(app)
    human = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body()).json()
    monkeypatch.delenv('DEEPGRAM_API_KEY', raising=False)
    with patch('core.stt_service.STTRegistry.get') as provider:
        cached = client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={})
        assert cached.status_code == 200
        assert cached.json()['reference'] == human['reference']
        assert cached.json()['review'] == human['review']
        provider.assert_not_called()
    STTReviewStore().delete_run(RUN['run_id'])
    assert client.post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={}).status_code == 422


def test_stt_evidence_survives_a_missing_primary_report():
    seed_recording()
    client = TestClient(app)
    with patch.dict(RUN['evaluation'], {'report': None}):
        evaluated = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS,
                                json=human_body())
        assert evaluated.status_code == 200
        response = client.get('/api/v1/runs/run-stt', headers=HEADERS)
    assert response.status_code == 200
    report = response.json()['evaluation']['report']['stt_quality']
    assert report['metric_kind'] == 'wer'
    assert report['evidence'][0]['status'] == 'confirmed_error'


def test_confirmed_alignment_survives_reload_and_is_reused_without_retyping():
    seed_recording()
    client = TestClient(app)
    first = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body())
    assert first.status_code == 200
    expected = first.json()['review']
    saved = client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()
    assert saved['audio']['scope'] == 'caller_only'
    assert saved['bolna']['segments'][0]['start'] == 0
    repeated = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json={})
    assert repeated.json()['review'] == expected
    other = client.get('/api/v1/runs/run-stt/stt-review', headers={'X-API-Key': 'other-key'}).json()
    assert other['bolna']['segments'][0]['start'] is None
    assert other['audio']['scope'] == 'unknown'


def test_confirmed_automatic_speaker_mapping_is_saved_without_changing_provenance():
    seed_recording()
    STTReviewStore().save(OWNER, RUN['run_id'], reference={
        'source': 'deepgram', 'scope': 'unknown', 'audio_sha256': HASH,
        'segments': [Segment(text='I do not want a refund', speaker='dg_7', start=0, end=3).model_dump()]})
    body = human_body()
    body.pop('human_reference')
    body.update(speaker_roles={'dg_7': 'caller'}, speaker_mapping_confirmed=True)
    client = TestClient(app)
    first = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=body).json()
    assert first['reference']['segments'][0]['role'] == 'caller'
    assert first['reference']['source'] == 'deepgram'
    assert not first['reference']['human_verified']
    repeated = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json={}).json()
    assert repeated['review']['metric_kind'] == 'estimated_disagreement'
    assert repeated['review']['metric_value'] == first['review']['metric_value']


def test_private_report_hydration_is_not_cacheable():
    seed_recording()
    client = TestClient(app)
    assert client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body()).status_code == 200
    assert client.get('/api/v1/runs/run-stt', headers=HEADERS).headers.get('cache-control') == 'no-store'


def test_caller_only_review_preserves_annotations_for_both_original_speakers():
    seed_recording()
    with patch.dict(RUN['evaluation'], {'raw_transcript': 'assistant: Hello\nuser: I do want a refund'}):
        body = human_body()
        for index, segment in enumerate(body['bolna_annotations']['segments']):
            segment.update(start=index * 3, end=index * 3 + 2)
        body['recording_scope'] = 'mixed'
        body['human_reference']['segments'][0].update(start=3, end=5)
        client = TestClient(app)
        first = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=body)
        assert first.status_code == 200
        saved = client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()
        assert len(saved['bolna']['segments']) == 2
        assert all(segment['start'] is not None for segment in saved['bolna']['segments'])


def test_saved_annotations_are_rejected_when_source_words_change():
    seed_recording()
    client = TestClient(app)
    assert client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body()).status_code == 200
    with patch.dict(RUN['evaluation'], {'raw_transcript': 'user: Different source words'}):
        saved = client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()
        report = client.get('/api/v1/runs/run-stt', headers=HEADERS).json()
    assert saved['bolna']['segments'][0]['text'] == 'Different source words'
    assert saved['bolna']['segments'][0]['start'] is None
    assert saved['review']['metric_value'] is None
    assert saved['review']['findings'] == []
    assert report['evaluation']['report']['stt_quality']['metric_value'] is None


def test_invalid_saved_original_source_is_not_echoed_by_reference_endpoint():
    corrupted = copy.deepcopy(RUN)
    canary = 'SYNTHETIC_PRIVATE_SAVED_SOURCE'
    corrupted['evaluation']['stt_source'] = {'source': 'bolna', 'segments': [
        {'speaker': 'source', 'text': {'x': canary}},
    ]}
    store = AsyncMock()
    store.get_run.return_value = corrupted
    with patch('api.routes.get_monitoring_store', return_value=store):
        response = TestClient(app).post('/api/v1/runs/run-stt/stt-review/reference', headers=HEADERS, json={})
    assert response.status_code == 422
    assert canary not in response.text
    assert 'input_value' not in response.text


def test_old_scored_review_is_withheld_until_recompared_without_losing_reference():
    seed_recording()
    client = TestClient(app)
    scored = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body())
    assert scored.status_code == 200
    stored = STTReviewStore().read(OWNER, RUN['run_id'])
    legacy = copy.deepcopy(stored['review'])
    legacy.pop('comparison_version', None)
    STTReviewStore().save(OWNER, RUN['run_id'], review=legacy)
    reloaded = client.get('/api/v1/runs/run-stt/stt-review', headers=HEADERS).json()
    assert reloaded['review']['metric_value'] is None
    assert not reloaded['review']['findings']
    assert reloaded['reference'] == stored['reference']
    assert reloaded['audio']['available']
    assert any('scoring rules' in issue for issue in reloaded['review']['issues'])
    refreshed = client.post('/api/v1/runs/run-stt/stt-review', headers=HEADERS, json=human_body()).json()
    assert refreshed['review']['metric_value'] == 1 / 6
    assert refreshed['review']['comparison_version'] == 'signed_numbers_v2'
