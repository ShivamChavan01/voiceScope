"""Deleting a private call must also remove its indexed transcript context."""
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient


async def test_call_deletion_purges_only_its_semantic_entry(monkeypatch, tmp_path):
    import api.routes
    import main
    import middleware.auth
    from storage import semantic_index
    from storage.monitoring import MonitoringStore

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path / 'semantic.sqlite'))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.delenv('MONITORING_DB_PATH', raising=False)
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-operator'}))
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)
    monkeypatch.setattr(semantic_index, 'embed', lambda texts: [np.ones(384, dtype='<f4') for _ in texts])
    await MonitoringStore().log_run({'run_id': 'delete-me', 'raw_transcript': 'Synthetic private call'})
    index = semantic_index.SemanticCollection('voice_calls')
    index.upsert(ids=['delete-me', 'keep-me'], documents=['Synthetic private call', 'Unrelated synthetic call'])
    response = TestClient(main.app).delete('/api/v1/runs/delete-me', headers={'X-API-Key': 'synthetic-operator'})
    assert response.status_code == 200
    assert index.get()['ids'] == ['keep-me']
    assert await MonitoringStore().get_run('delete-me') is None


async def test_index_deletion_failure_preserves_run_for_retry(monkeypatch, tmp_path):
    import api.routes
    import main
    import middleware.auth
    from storage.monitoring import MonitoringStore

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.delenv('MONITORING_DB_PATH', raising=False)
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-operator'}))
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)
    await MonitoringStore().log_run({'run_id': 'retry-delete', 'raw_transcript': 'Synthetic private call'})
    with patch('storage.semantic_index.SemanticCollection.delete', side_effect=OSError('private-canary')):
        response = TestClient(main.app, raise_server_exceptions=False).delete('/api/v1/runs/retry-delete', headers={'X-API-Key': 'synthetic-operator'})
    assert response.status_code == 503
    assert 'private-canary' not in response.text
    assert await MonitoringStore().get_run('retry-delete') is not None
