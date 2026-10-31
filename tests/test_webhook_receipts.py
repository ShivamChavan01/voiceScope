from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from storage.webhook_receipts import WebhookReceipts


def test_completion_survives_reopening_without_retaining_call_content(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    store = WebhookReceipts()
    state, token = store.claim('synthetic-call')
    assert state == 'claimed'
    store.complete('synthetic-call', token, 'synthetic-run')
    assert WebhookReceipts().claim('synthetic-call') == ('completed', 'synthetic-run')
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_atomic_claim_and_retry_after_failure(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    store = WebhookReceipts()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.claim('same-call'), range(2)))
    assert sorted(state for state, _ in results) == ['claimed', 'processing']
    token = next(token for state, token in results if state == 'claimed')
    store.release('same-call', 'wrong-token')
    assert store.claim('same-call')[0] == 'processing'
    store.release('same-call', token)
    assert store.claim('same-call')[0] == 'claimed'


def test_stale_worker_cannot_complete_or_remove_new_lease(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    store = WebhookReceipts()
    with patch('storage.webhook_receipts.time.time', return_value=100):
        _, old_token = store.claim('call')
    with patch('storage.webhook_receipts.time.time', return_value=701):
        _, token = store.claim('call')
        with pytest.raises(ValueError, match='lease changed'):
            store.complete('call', old_token, 'old-run')
        store.release('call', old_token)
        assert store.claim('call')[0] == 'processing'
    with pytest.raises(ValueError, match='run ID'):
        store.complete('call', token, '')
    store.complete('call', token, 'new-run')
    store.release('call', token)
    assert store.claim('call') == ('completed', 'new-run')
