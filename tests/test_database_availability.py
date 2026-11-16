"""Configured PostgreSQL failures must never select a different local dataset."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from storage import db
from storage.cost_store import CostStore
from storage.monitoring import MonitoringStore


@pytest.fixture
def unavailable_database(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://synthetic:private-canary@localhost/test')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setattr(db, '_pool', None)
    monkeypatch.setattr(db, '_pool_lock', None)
    monkeypatch.setattr(db.asyncpg, 'create_pool', AsyncMock(side_effect=OSError('private-canary')))
    return tmp_path


@pytest.mark.parametrize('operation', ['list', 'detail', 'write', 'delete', 'cost'])
async def test_unavailable_postgres_does_not_read_or_write_sqlite(unavailable_database, operation):
    store = MonitoringStore()
    with pytest.raises(RuntimeError, match='Configured PostgreSQL is unavailable') as caught:
        if operation == 'list':
            await store.get_runs()
        elif operation == 'detail':
            await store.get_run('synthetic-run')
        elif operation == 'write':
            await store.log_run({'run_id': 'synthetic-run'})
        elif operation == 'delete':
            await store.delete_run('synthetic-run')
        else:
            await CostStore().log_cost('synthetic-run', 'synthetic', 'none', 0, 0, 0)
    assert 'private-canary' not in str(caught.value)
    assert list(unavailable_database.iterdir()) == []


async def test_failed_startup_does_not_yield_a_healthy_application(unavailable_database, monkeypatch):
    import main

    monkeypatch.setattr(main, 'demo_enabled', lambda: False)
    with pytest.raises(RuntimeError, match='Configured PostgreSQL is unavailable'):
        async with main.lifespan(main.app):
            pytest.fail('Startup succeeded without the configured database')


def test_runtime_database_failure_is_private_retryable_503(unavailable_database, monkeypatch):
    import main
    import api.routes
    import middleware.auth

    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-operator-key'}))
    monkeypatch.setattr(api.routes, 'get_monitoring_store', MonitoringStore)
    monkeypatch.setenv('STAGING_DEMO_ONLY', 'false')
    monkeypatch.setenv('PUBLIC_SYNTHETIC_DEMO', 'false')
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get('/api/v1/runs', headers={'X-API-Key': 'synthetic-operator-key'})
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'
    assert 'private-canary' not in response.text
    assert 'database' in response.json()['detail'].lower()
    assert list(unavailable_database.iterdir()) == []


def test_dropped_established_connection_is_also_retryable(unavailable_database, monkeypatch):
    from unittest.mock import MagicMock
    import main
    import api.routes
    import middleware.auth

    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-operator-key'}))
    store = MonitoringStore()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(
        side_effect=db.asyncpg.PostgresConnectionError('private-canary'))
    monkeypatch.setattr(store, '_get_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(api.routes, 'get_monitoring_store', lambda: store)
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get('/api/v1/runs', headers={'X-API-Key': 'synthetic-operator-key'})
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'
    assert 'private-canary' not in response.text
    assert list(unavailable_database.iterdir()) == []


async def test_schema_failure_blocks_startup_and_closes_pool(unavailable_database, monkeypatch):
    import main

    monkeypatch.setattr(main, 'demo_enabled', lambda: False)
    monkeypatch.setattr(main, 'init_schema', AsyncMock(side_effect=RuntimeError('synthetic schema failure')))
    close = AsyncMock()
    monkeypatch.setattr(main, 'close_pool', close)
    with pytest.raises(RuntimeError, match='Configured PostgreSQL is unavailable'):
        async with main.lifespan(main.app):
            pytest.fail('Startup succeeded without schema initialization')
    close.assert_awaited_once()


async def test_connection_can_recover_on_later_request(unavailable_database, monkeypatch):
    pool = AsyncMock()
    pool._closed = False
    connect = AsyncMock(side_effect=[OSError('private-canary'), pool])
    monkeypatch.setattr(db.asyncpg, 'create_pool', connect)
    with pytest.raises(RuntimeError, match='Configured PostgreSQL is unavailable'):
        await db.get_pool()
    assert await db.get_pool() is pool
    assert await db.get_pool() is pool
    assert connect.await_count == 2


async def test_cancelled_connection_attempt_is_not_swallowed(unavailable_database, monkeypatch):
    monkeypatch.setattr(db.asyncpg, 'create_pool', AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await db.get_pool()


async def test_connection_attempt_has_a_bounded_total_timeout(unavailable_database, monkeypatch):
    cancelled = asyncio.Event()

    async def stalled_connect(*args, **kwargs):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    monkeypatch.setattr(db, 'CONNECT_TIMEOUT_SECONDS', 0.01)
    monkeypatch.setattr(db.asyncpg, 'create_pool', stalled_connect)
    with pytest.raises(RuntimeError, match='Configured PostgreSQL is unavailable'):
        await asyncio.wait_for(db.get_pool(), timeout=1)
    assert cancelled.is_set()
    assert db._pool is None
