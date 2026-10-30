import pytest

from core.knowledge_store import KnowledgeStore
from storage.cost_store import CostStore
from storage.monitoring import MonitoringStore


@pytest.mark.parametrize('override', [False, True])
async def test_run_storage_initializes_missing_parent_and_preserves_saved_data(monkeypatch, tmp_path, override):
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'new-data'))
    monkeypatch.delenv('MONITORING_DB_PATH', raising=False)
    if override:
        monkeypatch.setenv('MONITORING_DB_PATH', str(tmp_path / 'custom' / 'nested' / 'runs.db'))
    store = MonitoringStore()
    await store.log_run({'run_id': 'synthetic-path-run', 'status': 'completed', 'raw_transcript': 'Synthetic storage test'})
    restored = await MonitoringStore().get_run('synthetic-path-run')
    assert restored['evaluation']['raw_transcript'] == 'Synthetic storage test'


@pytest.mark.parametrize('override', [False, True])
async def test_cost_storage_initializes_missing_parent(monkeypatch, tmp_path, override):
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'new-data'))
    monkeypatch.delenv('COST_DB_PATH', raising=False)
    if override:
        monkeypatch.setenv('COST_DB_PATH', str(tmp_path / 'custom' / 'nested' / 'costs.db'))
    store = CostStore()
    await store.log_cost('synthetic-cost-run', 'synthetic', 'fixture', 0, 0, 0.0)
    summary = await CostStore().get_summary()
    assert summary['overall']['total_calls'] == 1


@pytest.mark.parametrize('override', [False, True])
async def test_knowledge_storage_initializes_missing_parent(monkeypatch, tmp_path, override):
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'new-data'))
    monkeypatch.delenv('KNOWLEDGE_DB_PATH', raising=False)
    if override:
        monkeypatch.setenv('KNOWLEDGE_DB_PATH', str(tmp_path / 'custom' / 'nested' / 'knowledge.db'))
    store = KnowledgeStore()
    try:
        await store.add_entry('Synthetic policy', 'Synthetic test-only content')
        assert (await store.list_entries())[0]['content'] == 'Synthetic test-only content'
    finally:
        store._conn.close()
