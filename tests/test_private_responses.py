import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.mark.parametrize('path', ['/api/v1/runs', '/api/v1/policies', '/api/v1/knowledge', '/api/v1/runs/missing/stt-review/audio', '/api/v1/webhooks/call-completed'])
def test_sensitive_routes_require_key_and_disable_caching(monkeypatch, path):
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-private-key'}))
    response = TestClient(app).get(path)
    assert response.status_code == 401
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {'detail': 'Invalid or missing API key'}


def test_authenticated_not_found_and_unconfigured_auth_are_not_cacheable(monkeypatch):
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-private-key'}))
    client = TestClient(app)
    response = client.get('/api/v1/absent', headers={'X-API-Key': 'synthetic-private-key'})
    assert response.status_code == 404
    assert response.headers['cache-control'] == 'no-store'
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset())
    response = client.get('/api/v1/runs')
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'


def test_request_validation_does_not_echo_private_transcript(monkeypatch):
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-private-key'}))
    response = TestClient(app).post('/api/v1/analyze-text', headers={'X-API-Key': 'synthetic-private-key'},
        json={'transcript': 'synthetic-private-caller-token' + 'x' * 60001})
    assert response.status_code == 422
    assert 'synthetic-private-caller-token' not in response.text
    assert response.json()['detail'][0]['loc'] == ['body', 'transcript']


def test_report_storage_failure_is_actionable_and_private(monkeypatch):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    import api.routes
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-private-key'}))
    pipeline = SimpleNamespace(run_from_transcript=AsyncMock(return_value={'run_id': 'synthetic', 'status': 'completed'}))
    monkeypatch.setattr(api.routes, 'get_pipeline', lambda: pipeline)
    monkeypatch.setattr(api.routes, '_log_cost', AsyncMock())
    monkeypatch.setattr(api.routes, '_log_metrics', AsyncMock())
    monkeypatch.setattr(api.routes, 'get_monitoring_store', lambda: SimpleNamespace(log_run=AsyncMock(side_effect=OSError('synthetic-private-database-token'))))
    response = TestClient(app).post('/api/v1/analyze-text', headers={'X-API-Key': 'synthetic-private-key'}, json={'transcript': 'Synthetic transcript'})
    assert response.status_code == 503
    assert 'could not be saved' in response.json()['detail']
    assert 'synthetic-private-database-token' not in response.text
