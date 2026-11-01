"""Isolated staging must never acquire a live provider or production database."""

import hashlib
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def demo_env(monkeypatch, tmp_path):
    import middleware.auth

    key = 'synthetic-staging-key-at-least-32-characters'
    monkeypatch.setenv('STAGING_DEMO_ONLY', 'true')
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('VALID_API_KEYS', key)
    for name in ['MONITORING_DB_PATH', 'POLICY_DB_PATH', 'KNOWLEDGE_DB_PATH', 'COST_DB_PATH',
                 'QA_DB_PATH', 'EXTRACTIONS_DB_PATH', 'OPTIMIZER_DB_PATH', 'STT_REVIEW_DIR',
                 'CHROMA_PERSIST_DIR', 'DEEPGRAM_API_KEY', 'BOLNA_API_KEY', 'GROQ_API_KEY',
                 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'MISTRAL_API_KEY',
                 'OPENCODE_GO_API_KEY', 'OPENROUTER_API_KEY']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({key}))
    return key, tmp_path


def test_demo_mode_blocks_cached_stt_provider(demo_env, monkeypatch):
    from stt_providers.registry import STTRegistry

    monkeypatch.setattr(STTRegistry, '_instances', {'deepgram': AsyncMock()})
    with pytest.raises(RuntimeError, match='demo'):
        STTRegistry.get('deepgram')


async def test_demo_mode_blocks_cached_llm_provider(demo_env, monkeypatch):
    from llm_providers.registry import ProviderRegistry

    provider = AsyncMock()
    monkeypatch.setattr(ProviderRegistry, '_instances', {'groq': provider})
    with pytest.raises(RuntimeError, match='demo'):
        await ProviderRegistry.call('groq', prompt='Synthetic')
    provider.complete.assert_not_called()


async def test_demo_mode_blocks_recording_network_before_connecting(demo_env):
    from core.stt_recording import download_recording

    with patch('aiohttp.ClientSession', side_effect=AssertionError('Network forbidden')):
        with pytest.raises(RuntimeError, match='demo'):
            await download_recording('https://example.com/synthetic.wav')


def test_demo_mode_blocks_reference_configuration_even_with_a_key(demo_env, monkeypatch):
    from core.stt_service import state_for_run

    monkeypatch.setenv('DEEPGRAM_API_KEY', 'synthetic-accidental-key')
    assert state_for_run({'evaluation': {}}, None)['provider']['configured'] is False


@pytest.mark.parametrize('path', [
    '/api/v1/analyze-text', '/api/v1/analyze', '/api/v1/analyze/stream',
    '/api/v1/batch', '/api/v1/webhooks/call-completed',
    '/api/v1/runs/demo-staging-stt/stt-review/reference',
    '/api/v1/runs/demo-staging-stt/stt-review/recording',
])
def test_live_routes_are_explicitly_disabled_after_auth(demo_env, path):
    from main import app

    client = TestClient(app)
    assert client.post(path).status_code == 401
    response = client.post(path, headers={'X-API-Key': demo_env[0]}, json={})
    assert response.status_code == 503
    assert 'demo' in response.json()['detail'].lower()
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('setting,value', [
    ('DATABASE_URL', 'postgresql://synthetic.invalid/production'),
    ('MONITORING_DB_PATH', '/outside-staging/monitoring.db'),
    ('VALID_API_KEYS', 'short'),
    ('DATA_DIR', '/'),
    ('DEEPGRAM_API_KEY', 'synthetic-provider-key'),
    ('OPENROUTER_API_KEY', 'synthetic-provider-key'),
])
def test_demo_rejects_unsafe_environment_before_storage(demo_env, monkeypatch, setting, value):
    from core.staging import validate_demo_environment

    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError):
        validate_demo_environment()
    assert not list(demo_env[1].rglob('*.db'))


def test_startup_rejects_external_database_before_connecting(demo_env, monkeypatch):
    import main

    monkeypatch.setenv('DATABASE_URL', 'postgresql://synthetic.invalid/production')
    with patch('main.init_schema', new_callable=AsyncMock) as connect:
        with pytest.raises(ValueError, match='external database'):
            with TestClient(main.app):
                pass
    connect.assert_not_called()


async def test_staging_seed_is_deterministic_and_reseeds_only_synthetic_data(demo_env):
    from core.staging_demo import seed_staging_demo, staging_scenarios
    from storage.monitoring import MonitoringStore
    from storage.stt_reviews import STTReviewStore

    scenarios = staging_scenarios()
    assert scenarios == staging_scenarios()
    assert len(scenarios) == 6
    with patch('llm_providers.registry.ProviderRegistry.get', side_effect=AssertionError('Provider forbidden')), \
         patch('stt_providers.registry.STTRegistry.get', side_effect=AssertionError('Provider forbidden')):
        await seed_staging_demo()
        await seed_staging_demo()
    store = MonitoringStore()
    assert (await store.get_runs(limit=50))['total'] == 6
    for run in scenarios:
        assert run['data_source'] == 'synthetic_demo'
        assert run['provider']['name'] == 'synthetic'
        assert run['report']['quality_score'] is None
        assert run['provider']['cost_usd'] == 0
    owner = hashlib.sha256(demo_env[0].encode()).hexdigest()
    artifacts = STTReviewStore()
    scored = artifacts.read(owner, 'demo-staging-stt')
    assert scored['reference']['source'] == 'synthetic'
    assert scored['review']['metric_kind'] == 'estimated_disagreement'
    assert scored['review']['metric_value'] == pytest.approx(.2)
    assert scored['review']['findings'][0]['status'] == 'needs_review'
    assert any('Synthetic authored' in item for item in scored['review']['limitations'])
    assert 'amount' in scored['review']['findings'][0]['category']
    blocked = artifacts.read(owner, 'demo-staging-not-scored')
    assert blocked['review']['metric_value'] is None
    assert any('Timestamps' in issue for issue in blocked['review']['issues'])
    assert blocked['review']['findings'][0]['status'] == 'needs_review'
    assert artifacts.read('another-owner', 'demo-staging-stt') is None
    with sqlite3.connect(artifacts.path) as connection:
        connection.execute('UPDATE stt_artifacts SET expires=0')
    assert artifacts.read(owner, 'demo-staging-stt') is None
    await seed_staging_demo()
    assert artifacts.read(owner, 'demo-staging-stt')['audio'] == scored['audio']
    await store.delete_run('demo-staging-policy')
    await seed_staging_demo()
    assert (await store.get_runs(limit=50))['total'] == 6


def test_startup_restores_fixtures_and_private_report_hydration(demo_env):
    from main import app

    with TestClient(app) as client:
        headers = {'X-API-Key': demo_env[0], 'X-STT-Review': '1'}
        response = client.get('/api/v1/runs', headers=headers)
        assert response.status_code == 200
        assert response.json()['total'] == 6
        run = client.get('/api/v1/runs/demo-staging-stt', headers=headers).json()
        assert run['evaluation']['report']['stt_quality']['metric_value'] == pytest.approx(.2)
        audio = client.get('/api/v1/runs/demo-staging-stt/stt-review/audio', headers=headers)
        assert audio.status_code == 200
        assert audio.content.startswith(b'RIFF')
        assert audio.headers['cache-control'] == 'no-store'
        seed = client.post('/api/v1/demo/staging', headers=headers)
        assert seed.status_code == 200
        assert seed.json()['seeded'] == 6


def test_staging_seed_route_is_unavailable_outside_demo(demo_env, monkeypatch):
    from main import app

    monkeypatch.delenv('STAGING_DEMO_ONLY')
    response = TestClient(app).post('/api/v1/demo/staging', headers={'X-API-Key': demo_env[0]})
    assert response.status_code == 404


def test_synthetic_audio_has_reproducible_provenance():
    import json
    import base64
    import zlib
    from core.stt_recording import inspect_recording

    fixture = json.loads((Path(__file__).resolve().parents[1] / 'core/data/staging_audio.json').read_text())
    audio = zlib.decompress(base64.b64decode(fixture['audio_zlib_base64']))
    info = inspect_recording(audio)
    assert info.sha256 == fixture['sha256']
    assert info.duration_seconds > 2
    assert fixture['synthetic'] is True
    assert fixture['generator'].startswith('eSpeak')
