from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.staging_demo import staging_scenarios
from storage.monitoring import MonitoringStore


@pytest.fixture
async def seeded(monkeypatch, tmp_path):
    import api.routes
    import middleware.auth
    import middleware.rate_limit
    from main import app
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'runs.db'))
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'ux-test'}))
    monkeypatch.setattr(middleware.rate_limit, 'RATE_LIMIT', 10000)
    store = MonitoringStore()
    monkeypatch.setattr(api.routes, 'get_monitoring_store', lambda: store)
    for sample in staging_scenarios():
        await store.log_run(sample)
    return store, TestClient(app)


@pytest.mark.parametrize('assessment,expected', [('policy_matches', 2), ('no_matches', 1),
    ('not_assessed', 3), ('needs_review', 0), ('insufficient_evidence', 0)])
async def test_canonical_assessment_filters_are_independent_of_processing(seeded, assessment, expected):
    store, client = seeded
    response = client.get('/api/v1/runs', params={'assessment': assessment, 'status': 'completed'}, headers={'X-API-Key': 'ux-test'})
    assert response.status_code == 200
    assert response.json()['total'] == expected
    assert len(response.json()['runs']) == expected
    assert all(row['status'] == 'completed' for row in response.json()['runs'])
    assert (await store.get_run_summary())['total_calls'] == 6


@pytest.mark.parametrize('search,count', [('refund', 1), ('nothing matches 雪', 0), ('demo-staging-escalation', 1)])
async def test_assessment_search_and_pagination_use_the_same_result_set(seeded, search, count):
    _, client = seeded
    response = client.get('/api/v1/runs', params={'assessment': 'policy_matches', 'search': search, 'limit': 1}, headers={'X-API-Key': 'ux-test'})
    assert response.status_code == 200
    assert response.json()['total'] == count


async def test_filtering_precedes_pagination_and_preserves_actual_processing(seeded):
    store, client = seeded
    sample = staging_scenarios()[1]
    sample['status'] = 'partial'
    await store.log_run(sample)
    response = client.get('/api/v1/runs?assessment=policy_matches&status=partial', headers={'X-API-Key': 'ux-test'})
    assert response.json()['total'] == 1
    assert response.json()['runs'][0]['run_id'] == sample['run_id']
    response = client.get('/api/v1/runs?assessment=policy_matches&limit=1&offset=1', headers={'X-API-Key': 'ux-test'})
    assert response.json()['total'] == 2
    assert len(response.json()['runs']) == 1
    response = client.get('/api/v1/runs?assessment=not_assessed&offset=999', headers={'X-API-Key': 'ux-test'})
    assert response.json()['total'] == 3
    assert response.json()['runs'] == []


@pytest.mark.parametrize('query', ['assessment=clean', 'assessment=garbage', 'status=review_required', 'status=garbage'])
async def test_invalid_filter_parameters_are_validation_errors(seeded, query):
    _, client = seeded
    assert client.get('/api/v1/runs?'+query, headers={'X-API-Key': 'ux-test'}).status_code == 422


async def test_existing_summary_counts_are_real_only_and_reconcile(seeded):
    store, _ = seeded
    summary = await store.get_run_summary()
    rows = (await store.get_runs(limit=200))['runs']
    assert summary['total_calls'] == summary['demo_calls'] + summary['real_calls'] == len(rows) == 6
    assert summary['legacy_calls'] == summary['confirmed_policy_calls'] == summary['evaluated_policy_calls'] == 0
    assert sum(row['reliability_summary'] is None for row in rows) == 3
    for sample in staging_scenarios():
        sample['run_id'] = sample['run_id'].replace('demo-staging-', 'real-')
        await store.log_run(sample)
    summary = await store.get_run_summary()
    assert summary['real_calls'] == summary['demo_calls'] == 6
    assert summary['total_calls'] == 12
    assert summary['legacy_calls'] == 3
    assert summary['confirmed_policy_calls'] == 2
    assert summary['evaluated_policy_calls'] == 3


async def test_empty_and_real_only_data_keep_the_same_scopes(seeded):
    store, _ = seeded
    for sample in staging_scenarios():
        await store.delete_run(sample['run_id'])
    summary = await store.get_run_summary()
    assert summary['total_calls'] == summary['real_calls'] == summary['legacy_calls'] == 0
    assert (await store.get_runs(assessment='not_assessed'))['total'] == 0
    for sample in staging_scenarios():
        sample['run_id'] = sample['run_id'].replace('demo-staging-', 'real-')
        await store.log_run(sample)
    summary = await store.get_run_summary()
    assert summary['total_calls'] == summary['real_calls'] == 6
    assert summary['demo_calls'] == 0
    assert summary['legacy_calls'] == 3
    assert (await store.get_runs(assessment='policy_matches'))['total'] == 2


async def test_malformed_or_insufficient_reports_cannot_become_no_matches(seeded):
    from core.reliability import evaluate_reliability
    store, _ = seeded
    await store.log_run({'run_id': 'broken', 'reliability': {'status': 'invalid'}})
    await store.log_run({'run_id': 'insufficient', 'reliability': {'status': 'insufficient_evidence'}})
    report = evaluate_reliability([{'role': 'agent', 'role_source': 'transcript_label', 'text': 'I have completed your refund.'}], [])
    await store.log_run({'run_id': 'unverified', 'reliability': report.model_dump()})
    assert (await store.get_runs(assessment='not_assessed'))['total'] == 4
    assert (await store.get_runs(assessment='insufficient_evidence'))['total'] == 1
    assert (await store.get_runs(assessment='needs_review'))['total'] == 1
    clear = await store.get_runs(assessment='no_matches')
    assert clear['total'] == 1
    assert clear['runs'][0]['reliability_summary']['checked_rule_count'] == 2


async def test_assessment_count_and_offset_cover_rows_beyond_the_first_batch(seeded):
    store, _ = seeded
    for n in range(201):
        await store.log_run({'run_id': f'old-{n}', 'status': 'completed'})
    result = await store.get_runs(limit=1, offset=1, assessment='policy_matches')
    assert result['total'] == 2
    assert len(result['runs']) == 1
    assert (await store.get_runs(limit=2, offset=200, assessment='not_assessed'))['total'] == 204


async def test_postgres_path_reuses_the_validated_summary_filter(seeded, monkeypatch):
    store, _ = seeded
    rows = (await store.get_runs(limit=200))['runs']
    pool = object()
    monkeypatch.setattr(store, '_get_pool', AsyncMock(return_value=pool))
    method = AsyncMock(return_value={'runs': rows, 'total': 6, 'limit': 200, 'offset': 0})
    monkeypatch.setattr(store, '_get_runs_pg', method)
    result = await store.get_runs(limit=1, search='demo-staging', status='completed', assessment='policy_matches')
    assert result['total'] == 2
    assert len(result['runs']) == 1
    method.assert_awaited_once_with(pool, 200, 0, 'demo-staging', 'completed')


async def test_equal_timestamp_rows_have_stable_order_across_filtered_pages(seeded):
    store, _ = seeded
    with store._sqlite_conn() as conn:
        conn.execute("UPDATE runs SET created_at='2026-11-02 12:00:00'")
    first = await store.get_runs(limit=1, assessment='policy_matches')
    second = await store.get_runs(limit=1, offset=1, assessment='policy_matches')
    ids = [first['runs'][0]['run_id'], second['runs'][0]['run_id']]
    assert ids == sorted(['demo-staging-policy', 'demo-staging-escalation'], reverse=True)


async def test_postgres_batches_have_an_explicit_unique_sort_tiebreaker(seeded):
    from unittest.mock import MagicMock
    store, _ = seeded
    conn = AsyncMock()
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    await store._get_runs_pg(pool, 200, 0, None, None)
    assert 'ORDER BY created_at DESC, run_id DESC' in conn.fetch.call_args.args[0]
