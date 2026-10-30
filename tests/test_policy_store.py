import sqlite3

import pytest
from pydantic import ValidationError

from core.policy_store import PolicyStore
from core.reliability import PolicyRule


def policy(**updates):
    return PolicyRule(**{
        'id': 'refund', 'title': 'Refund policy', 'kind': 'no_same_day_refund_guarantee',
        'text': 'Agents must never guarantee same-day refunds.', **updates,
    })


async def test_empty_store_does_not_enable_demo_policy(tmp_path):
    store = PolicyStore(str(tmp_path / 'rules.db'))
    assert await store.list_rules() == []


async def test_rule_survives_reload_and_upsert_does_not_duplicate(tmp_path):
    path = str(tmp_path / 'rules.db')
    store = PolicyStore(path)
    first = policy()
    assert await store.upsert_rule(first) == first
    assert await PolicyStore(path).list_rules() == [first]
    updated = policy(title='New title', text='Agents must never promise same-day refunds.', enabled=False)
    await store.upsert_rule(updated)
    rows = await PolicyStore(path).list_rules()
    assert rows == [updated]
    assert rows[0].version != first.version


async def test_delete_rule_is_idempotent_and_safe(tmp_path):
    store = PolicyStore(str(tmp_path / 'rules.db'))
    await store.upsert_rule(policy())
    assert await store.delete_rule("refund' OR 1=1 --") is False
    assert len(await store.list_rules()) == 1
    assert await store.delete_rule('refund') is True
    assert await store.delete_rule('refund') is False
    assert await store.list_rules() == []


async def test_environment_path_and_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv('POLICY_DB_PATH', raising=False)
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'nested'))
    store = PolicyStore()
    assert store.db_path == str(tmp_path / 'nested' / 'policies.db')
    monkeypatch.setenv('POLICY_DB_PATH', str(tmp_path / 'explicit.db'))
    assert PolicyStore().db_path == str(tmp_path / 'explicit.db')


async def test_in_memory_store_retains_rules_until_closed():
    store = PolicyStore(':memory:')
    await store.upsert_rule(policy())
    assert await store.list_rules() == [policy()]
    store.close()
    store.close()


async def test_invalid_persisted_policy_fails_instead_of_activating(tmp_path):
    path = str(tmp_path / 'rules.db')
    store = PolicyStore(path)
    await store.upsert_rule(policy())
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE policy_rules SET text='Refunds are easy.'")
    with pytest.raises(ValidationError):
        await store.list_rules()
