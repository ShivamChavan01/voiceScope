import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from storage.monitoring import MonitoringStore
from storage.webhook_receipts import WebhookReceipts
from tools.sqlite_snapshot import main, snapshot_sqlite


def database(path):
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE calls (text TEXT)')
    connection.commit()
    return connection


def test_snapshot_preserves_committed_wal_and_excludes_uncommitted_data(tmp_path):
    source, backup = tmp_path / 'calls.db', tmp_path / 'private' / 'snapshot.sqlite'
    with closing(database(source)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute("INSERT INTO calls VALUES ('committed synthetic transcript')")
        writer.commit()
        assert Path(str(source) + '-wal').stat().st_size > 0
        writer.execute("INSERT INTO calls VALUES ('uncommitted')")
        snapshot_sqlite(source, backup)
        writer.rollback()
    with closing(sqlite3.connect(backup)) as restored:
        assert restored.execute('SELECT * FROM calls').fetchall() == [('committed synthetic transcript',)]
    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('kind', ['existing', 'same', 'symlink'])
def test_snapshot_never_overwrites_existing_destination(tmp_path, kind):
    source = tmp_path / 'source.db'
    database(source).close()
    destination = source if kind == 'same' else tmp_path / 'existing.db'
    if kind == 'existing':
        destination.write_bytes(b'preserve me')
    elif kind == 'symlink':
        destination.symlink_to(source)
    original = destination.read_bytes()
    with pytest.raises(FileExistsError):
        snapshot_sqlite(source, destination)
    assert destination.read_bytes() == original


@pytest.mark.parametrize('kind', ['missing', 'empty', 'corrupt', 'directory'])
def test_invalid_source_does_not_publish_a_backup(tmp_path, kind):
    source, destination = tmp_path / 'source', tmp_path / 'backup.db'
    if kind == 'directory':
        source.mkdir()
    elif kind != 'missing':
        source.write_bytes(b'' if kind == 'empty' else b'not sqlite')
    with pytest.raises((OSError, ValueError)):
        snapshot_sqlite(source, destination)
    assert not destination.exists()


def test_snapshot_failure_cleans_temporary_files_and_keeps_source(tmp_path):
    source, destination = tmp_path / 'source.db', tmp_path / 'snapshot.db'
    database(source).close()
    original = source.read_bytes()
    with patch('tools.sqlite_snapshot.os.link', side_effect=OSError('synthetic failure')):
        assert main([str(source), str(destination)]) == 1
    assert source.read_bytes() == original
    assert not destination.exists()
    assert not list(tmp_path.glob('.sqlite-snapshot-*'))


def test_locked_source_timeout_does_not_publish_partial_snapshot(tmp_path):
    source, destination = tmp_path / 'source.db', tmp_path / 'snapshot.db'
    database(source).close()
    with patch('tools.sqlite_snapshot.time.monotonic', side_effect=[0, 31]):
        with pytest.raises(TimeoutError):
            snapshot_sqlite(source, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob('.sqlite-snapshot-*'))


async def test_restored_run_and_receipt_survive_new_store_instances(monkeypatch, tmp_path):
    active, recovery = tmp_path / 'active', tmp_path / 'recovery'
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('DATA_DIR', str(active))
    monkeypatch.delenv('MONITORING_DB_PATH', raising=False)
    await MonitoringStore().log_run({'run_id': 'synthetic-run', 'raw_transcript': 'Synthetic transcript'})
    receipts = WebhookReceipts()
    _, token = receipts.claim('synthetic-execution')
    receipts.complete('synthetic-execution', token, 'synthetic-run')
    for source in [active / 'monitoring.db', receipts.path]:
        backup = tmp_path / 'backups' / source.name
        assert main([str(source), str(backup)]) == 0
        snapshot_sqlite(backup, recovery / source.relative_to(active))
    monkeypatch.setenv('DATA_DIR', str(recovery))
    run = await MonitoringStore().get_run('synthetic-run')
    assert run['evaluation']['raw_transcript'] == 'Synthetic transcript'
    assert WebhookReceipts().claim('synthetic-execution') == ('completed', 'synthetic-run')
