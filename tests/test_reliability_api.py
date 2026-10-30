from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.pipeline import VoiceScopePipeline
from core.harness import ValidationHarness
from main import app
from storage.monitoring import MonitoringStore

HEADERS = {'X-API-Key': 'reliability-test'}
RULE = {
    'id': 'refund-guarantee', 'title': 'Refund promises',
    'kind': 'no_same_day_refund_guarantee',
    'text': 'Agents must never guarantee same-day refunds.', 'enabled': True,
}


@pytest.fixture(autouse=True)
def isolated_rules(monkeypatch, tmp_path):
    import api.routes
    import middleware.auth

    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('POLICY_DB_PATH', str(tmp_path / 'policies.db'))
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'monitoring.db'))
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'reliability-test'}))
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)


def test_policy_configuration_is_opt_in_versioned_and_deletable():
    client = TestClient(app)
    assert client.get('/api/v1/policies/rules', headers=HEADERS).json() == []
    response = client.post('/api/v1/policies/rules', headers=HEADERS, json=RULE)
    assert response.status_code == 200
    version = response.json()['version']
    assert version
    assert client.get('/api/v1/policies/rules', headers=HEADERS).json()[0]['version'] == version
    updated = client.post('/api/v1/policies/rules', headers=HEADERS, json={**RULE, 'enabled': False})
    assert updated.status_code == 200
    assert updated.json()['enabled'] is False
    assert client.delete('/api/v1/policies/rules/refund-guarantee', headers=HEADERS).status_code == 200
    assert client.get('/api/v1/policies/rules', headers=HEADERS).json() == []
    assert client.delete('/api/v1/policies/rules/missing', headers=HEADERS).status_code == 404


@pytest.mark.parametrize('changes', [
    {'text': 'Refunds are allowed.'}, {'text': ''}, {'kind': 'invented'}, {'enabled': 'false'},
])
def test_invalid_policy_is_rejected(changes):
    response = TestClient(app).post('/api/v1/policies/rules', headers=HEADERS, json={**RULE, **changes})
    assert response.status_code == 422


def test_demo_is_idempotent_and_does_not_activate_policies():
    client = TestClient(app)
    response = client.post('/api/v1/demo/reliability', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['seeded'] == 3
    again = client.post('/api/v1/demo/reliability', headers=HEADERS)
    assert again.json()['run_ids'] == response.json()['run_ids']
    assert client.get('/api/v1/policies/rules', headers=HEADERS).json() == []
    rows = client.get('/api/v1/runs', headers=HEADERS).json()
    assert rows['total'] == 3
    assert all(row['reliability_summary'] is not None for row in rows['runs'])
    for row in rows['runs']:
        result = client.get('/api/v1/runs/' + row['run_id'], headers=HEADERS).json()
        assert result['evaluation']['speech_diagnostics']['time_to_first_audio_ms'] is None
        assert result['quality_score'] is None
    summary = client.get('/api/v1/runs/summary', headers=HEADERS).json()
    assert summary['real_calls'] == 0
    assert summary['confirmed_policy_calls'] == 0


async def test_policy_evidence_survives_model_failure_and_reload():
    from agents.speaker_agent import SpeakerAgent
    from core.policy_store import PolicyStore
    from core.reliability import PolicyRule

    await PolicyStore().upsert_rule(PolicyRule(**RULE))
    pipeline = VoiceScopePipeline.__new__(VoiceScopePipeline)
    pipeline.speaker_agent = SpeakerAgent.__new__(SpeakerAgent)
    pipeline.harness = ValidationHarness()

    async def failed_analysis(ctx):
        ctx.add_error('analysis', 'model offline')
        return ctx

    pipeline.analysis_agent = SimpleNamespace(run=failed_analysis)
    pipeline.report_agent = SimpleNamespace(run=AsyncMock())
    result = await pipeline.run_from_transcript('assistant: I guarantee a same-day refund.\nuser: Thank you.')
    pipeline.report_agent.run.assert_not_awaited()
    assert result['status'] == 'failed'
    findings = result['reliability']['findings']
    assert any(item['category'] == 'policy_violation' and item['status'] == 'confirmed' for item in findings)
    await MonitoringStore().log_run(result)
    loaded = await MonitoringStore().get_run(result['run_id'])
    assert loaded['evaluation']['reliability'] == result['reliability']


def test_bolna_diagnostics_survive_webhook_storage(monkeypatch):
    import api.routes

    pipeline = SimpleNamespace(run_from_transcript=AsyncMock(return_value={
        'run_id': 'diagnostic-call', 'report': {}, 'analysis': {},
    }))
    monkeypatch.setattr(api.routes, 'get_pipeline', lambda: pipeline)
    client = TestClient(app)
    response = client.post('/api/v1/webhooks/call-completed', headers=HEADERS, json={
        'id': 'source-id', 'agent_id': 'source-agent', 'status': 'completed',
        'transcript': 'assistant: Hello.\nuser: Hi.', 'conversation_duration': 5,
        'telephony_data': {'hangup_reason': 'Unknown', 'hangup_by': 'Caller'},
        'latency_data': {'time_to_first_audio': 136.2, 'interruption_stats': {'total_interruptions': 0}},
    })
    assert response.status_code == 200
    loaded = client.get('/api/v1/runs/diagnostic-call', headers=HEADERS).json()
    diagnostic = loaded['evaluation']['speech_diagnostics']
    assert diagnostic['source'] == 'bolna'
    assert diagnostic['time_to_first_audio_ms'] == 136.2
    assert diagnostic['total_interruptions'] == 0
    assert diagnostic['hangup_reason'] == 'Unknown'
