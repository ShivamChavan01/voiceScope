from unittest.mock import AsyncMock, MagicMock

import pytest

from storage.monitoring import MonitoringStore


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'monitoring.db'))
    return MonitoringStore()


async def test_summary_counts_persisted_runs_not_metrics_or_history(store):
    for n in range(16):
        await store.log_run({'run_id': f'call-{n}', 'status': 'completed'})
    summary = await store.get_run_summary()
    assert summary['total_calls'] == 16
    assert summary['real_calls'] == 16
    assert summary['demo_calls'] == 0
    assert (await store.get_runs(limit=5))['total'] == summary['total_calls']


async def test_demo_and_failed_runs_excluded_from_real_rates(store):
    await store.log_run({'run_id': 'demo-001', 'analysis': {'hallucination_detected': True}})
    await store.log_run({'run_id': 'failed-call', 'status': 'failed'})
    await store.log_run({'run_id': 'review-call', 'status': 'partial'})
    summary = await store.get_run_summary()
    assert summary['total_calls'] == 3
    assert summary['real_calls'] == 2
    assert summary['demo_calls'] == 1
    assert summary['evaluated_real_calls'] == 0
    assert summary['hallucination_rate'] is None
    await store.log_run({'run_id': 'real-call', 'analysis': {'hallucination_detected': True}})
    summary = await store.get_run_summary()
    assert summary['evaluated_real_calls'] == 1
    assert summary['hallucination_rate'] == 1
    assert (await store.get_run('review-call'))['status'] == 'partial'


async def test_full_evaluation_survives_reload(store):
    result = {
        'run_id': 'debug-call', 'raw_transcript': 'Agent: Hello. ' * 200,
        'status': 'partial', 'errors': ['analysis failed'],
        'harness': {'validation_passed': False, 'validation_errors': ['unsupported claim']},
    }
    await store.log_run(result)
    assert (await store.get_run('debug-call'))['evaluation'] == result


async def test_empty_summary_has_no_measured_rate(store):
    summary = await store.get_run_summary()
    assert summary['total_calls'] == 0
    assert summary['hallucination_rate'] is None


async def test_postgres_summary_uses_same_contract(store, monkeypatch):
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        'total_calls': 3, 'demo_calls': 1, 'real_calls': 2, 'completed_calls': 2,
        'flagged_calls': 1, 'escalated_calls': 0, 'evaluated_real_calls': 1,
    }
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    monkeypatch.setattr(store, '_get_pool', AsyncMock(return_value=pool))
    summary = await store.get_run_summary()
    assert summary['hallucination_rate'] == 1
    assert summary['scope'] == 'all_time_persisted_runs'


async def test_demo_reseed_is_idempotent_and_has_no_fake_model_metrics(store):
    from core.demo_seed import seed_demo_runs

    await seed_demo_runs(store)
    first = await store.get_run_summary()
    await seed_demo_runs(store)
    assert await store.get_run_summary() == first
    assert first['demo_calls'] == 8
    assert first['real_calls'] == 0
    demo = await store.get_run('demo-003')
    assert demo['provider'] == 'synthetic'
    assert demo['cost_usd'] == 0
    assert demo['quality_score'] is None
    assert demo['evaluation']['data_source'] == 'synthetic_demo'
    assert demo['truth_score'] == demo['evaluation']['harness']['truth_score']
    with store._sqlite_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM call_metrics').fetchone()[0] == 0
