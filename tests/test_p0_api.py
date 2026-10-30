from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

HEADERS = {'X-API-Key': 'test-key'}


@pytest.fixture(autouse=True)
def isolate_auth(monkeypatch):
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'test-key'}))


def test_summary_endpoint_uses_persisted_run_summary():
    store = AsyncMock()
    store.get_run_summary.return_value = {'total_calls': 16, 'scope': 'all_time_persisted_runs'}
    with patch('api.routes.get_monitoring_store', return_value=store):
        response = TestClient(app).get('/api/v1/runs/summary', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['total_calls'] == 16
    store.get_run_summary.assert_awaited_once()


def test_benchmark_returns_unmeasured_hallucination_metric():
    response = TestClient(app).get('/api/v1/loop/benchmark', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['total_tests'] == 10
    assert response.json()['hallucination_accuracy'] is None
    assert response.json()['hallucination_evaluated'] == 0


def test_missing_benchmark_is_unavailable_not_successful_zero():
    with patch('core.benchmark.HarnessBenchmark.run_benchmark', side_effect=FileNotFoundError):
        response = TestClient(app).get('/api/v1/loop/benchmark', headers=HEADERS)
    assert response.status_code == 503
