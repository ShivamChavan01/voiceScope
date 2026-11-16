"""Reject known storage outages before submitting a completed call to providers."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi.testclient import TestClient


def test_database_outage_does_not_start_bolna_evaluation(monkeypatch, tmp_path):
    import api.routes
    import main
    import middleware.auth
    from storage import db
    from storage.monitoring import MonitoringStore

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', 'postgresql://synthetic:private-canary@localhost/test')
    monkeypatch.setenv('STAGING_DEMO_ONLY', 'false')
    monkeypatch.setenv('PUBLIC_SYNTHETIC_DEMO', 'false')
    monkeypatch.delenv('STAGING_QA_AGENT_ID', raising=False)
    monkeypatch.setattr(db, '_pool', None)
    monkeypatch.setattr(db, '_pool_lock', None)
    monkeypatch.setattr(db.asyncpg, 'create_pool', AsyncMock(side_effect=OSError('private-canary')))
    monkeypatch.setattr(middleware.auth, '_WEBHOOK_KEY', 'synthetic-webhook-secret')
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)
    pipeline = AsyncMock()
    pipeline.run_from_transcript.return_value = {
        'run_id': 'synthetic-run', 'status': 'completed', 'report': {}, 'analysis': {}}
    monkeypatch.setattr(api.routes, 'get_pipeline', lambda: pipeline)

    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post('/api/v1/webhooks/call-completed',
        headers={'X-Webhook-Key': 'synthetic-webhook-secret'}, json={
            'id': 'synthetic-storage-outage', 'agent_id': 'synthetic-agent',
            'status': 'completed', 'transcript': 'assistant: Hello.\nuser: Hi.',
            'conversation_duration': 1, 'telephony_data': {}})

    assert response.status_code == 503
    assert 'private-canary' not in response.text
    pipeline.run_from_transcript.assert_not_awaited()
    pipeline.run.assert_not_awaited()


async def test_sqlite_connection_check_does_not_create_call_records(monkeypatch, tmp_path):
    from storage.monitoring import MonitoringStore

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.delenv('MONITORING_DB_PATH', raising=False)
    store = MonitoringStore()
    await store.check_connection()
    assert (await store.get_runs())['total'] == 0


async def test_sqlite_failure_is_sanitized_and_retryable(monkeypatch):
    from storage.db import DatabaseUnavailableError
    from storage.monitoring import MonitoringStore

    store = MonitoringStore()
    monkeypatch.setattr(store, '_get_pool', AsyncMock(return_value=None))
    monkeypatch.setattr(store, '_sqlite_conn', MagicMock(side_effect=sqlite3.OperationalError('private-canary')))
    with pytest.raises(DatabaseUnavailableError) as caught:
        await store.check_connection()
    assert 'private-canary' not in str(caught.value)


async def test_postgres_check_queries_an_established_connection(monkeypatch):
    from storage.monitoring import MonitoringStore

    store, pool = MonitoringStore(), MagicMock()
    connection = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=connection)
    monkeypatch.setattr(store, '_get_pool', AsyncMock(return_value=pool))
    await store.check_connection()
    connection.execute.assert_awaited_once_with('SELECT 1')
