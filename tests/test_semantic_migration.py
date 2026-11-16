import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from storage.semantic_index import SemanticCollection
from tools.semantic_migration import export_legacy, import_export, main


@pytest.fixture
def exported(monkeypatch, tmp_path):
    from storage import semantic_index
    monkeypatch.setattr(semantic_index, 'embed', lambda texts: [np.ones(384, dtype='<f4') for _ in texts])
    source = tmp_path / 'private.json'
    source.write_text(json.dumps({'format': 'voicescope-semantic-export-v1', 'collections': {
        'voice_calls': {'ids': ['original-call-id'], 'documents': ['Synthetic call transcript'], 'metadatas': [{'outcome': 'resolved'}]},
        'policy_kb': {'ids': ['policy_0'], 'documents': ['Synthetic policy'], 'metadatas': [{'chunk_index': 0}]}}}))
    return source


def test_import_preserves_ids_documents_metadata_and_source(exported, tmp_path):
    original = exported.read_bytes()
    destination = tmp_path / 'new-index.sqlite'
    assert import_export(exported, destination) == 2
    calls = SemanticCollection('voice_calls', destination)
    assert calls.get() == {'ids': ['original-call-id'], 'documents': ['Synthetic call transcript'], 'metadatas': [{'outcome': 'resolved'}]}
    assert exported.read_bytes() == original
    assert destination.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        import_export(exported, destination)
    assert calls.count() == 1


def test_combined_import_preserves_separate_legacy_corpora(exported, tmp_path):
    data = json.loads(exported.read_text())
    calls, policies = tmp_path / 'calls.json', tmp_path / 'policies.json'
    for path, name in [(calls, 'voice_calls'), (policies, 'policy_kb')]:
        path.write_text(json.dumps({'format': data['format'], 'collections': {name: data['collections'][name]}}))
    before = [path.read_bytes() for path in (calls, policies)]
    destination = tmp_path / 'combined.sqlite'
    assert main(['import', str(calls), str(destination), '--additional-source', str(policies)]) == 0
    assert SemanticCollection('voice_calls', destination).get()['ids'] == ['original-call-id']
    assert SemanticCollection('policy_kb', destination).get()['documents'] == ['Synthetic policy']
    assert [path.read_bytes() for path in (calls, policies)] == before


@pytest.mark.parametrize('conflict', ['document', 'metadata'])
def test_conflicting_duplicate_import_never_selects_a_side(exported, tmp_path, conflict):
    from tools.semantic_migration import import_export
    other = json.loads(exported.read_text())
    if conflict == 'document':
        other['collections']['voice_calls']['documents'][0] = 'Conflicting synthetic call'
    else:
        other['collections']['voice_calls']['metadatas'][0] = {'outcome': 'different'}
    source = tmp_path / 'conflicting.json'
    source.write_text(json.dumps(other))
    destination = tmp_path / 'combined.sqlite'
    with pytest.raises(ValueError, match='conflict'):
        import_export(exported, destination, additional_sources=[source])
    assert not destination.exists()


def test_identical_repeated_exports_are_imported_once(exported, tmp_path):
    destination = tmp_path / 'combined.sqlite'
    assert import_export(exported, destination, additional_sources=[exported]) == 2
    assert SemanticCollection('voice_calls', destination).count() == 1


def test_combined_size_limit_applies_to_all_sources(exported, monkeypatch, tmp_path):
    monkeypatch.setattr('tools.semantic_migration.MAX_EXPORT_BYTES', len(exported.read_bytes()) + 1)
    destination = tmp_path / 'combined.sqlite'
    with pytest.raises(ValueError, match='Combined exports'):
        import_export(exported, destination, additional_sources=[exported])
    assert not destination.exists()


def test_json_boolean_and_number_metadata_are_conflicting(exported, tmp_path):
    data = json.loads(exported.read_text())
    data['collections']['voice_calls']['metadatas'][0] = {'approved': 1}
    exported.write_text(json.dumps(data))
    other = tmp_path / 'boolean.json'
    data['collections']['voice_calls']['metadatas'][0] = {'approved': True}
    other.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='conflict'):
        import_export(exported, tmp_path / 'combined.sqlite', additional_sources=[other])


def test_duplicate_ids_inside_one_export_remain_invalid(exported, tmp_path):
    data = json.loads(exported.read_text())
    rows = data['collections']['voice_calls']
    for values in rows.values():
        values.append(values[0])
    exported.write_text(json.dumps(data))
    assert main(['import', str(exported), str(tmp_path / 'combined.sqlite')]) == 1
    assert not (tmp_path / 'combined.sqlite').exists()


def test_import_order_does_not_change_the_combined_data(exported, tmp_path):
    data = json.loads(exported.read_text())
    data['collections']['voice_calls']['ids'][0] = 'different-call-id'
    second = tmp_path / 'second.json'
    second.write_text(json.dumps(data))
    a, b = tmp_path / 'a.sqlite', tmp_path / 'b.sqlite'
    assert import_export(exported, a, additional_sources=[second]) == 3
    assert import_export(second, b, additional_sources=[exported]) == 3
    assert SemanticCollection('voice_calls', a).get() == SemanticCollection('voice_calls', b).get()


def test_duplicate_json_collection_keys_are_not_silently_overwritten(exported, tmp_path):
    data = json.loads(exported.read_text())
    rows = json.dumps(data['collections']['voice_calls'])
    second = rows.replace('original-call-id', 'different-call-id')
    source = tmp_path / 'ambiguous.json'
    source.write_text('{"format":"voicescope-semantic-export-v1","collections":{"voice_calls":'
        + rows + ',"voice_calls":' + second + '}}')
    destination = tmp_path / 'new-index.sqlite'
    assert main(['import', str(source), str(destination)]) == 1
    assert not destination.exists()


def test_legacy_upgrade_blocks_startup_until_explicit_import(exported, monkeypatch, tmp_path):
    from storage.semantic_index import validate_legacy_migration

    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    (legacy / 'chroma.sqlite3').write_bytes(b'untouched legacy data')
    destination = tmp_path / 'new-index.sqlite'
    monkeypatch.setenv('CHROMA_PERSIST_DIR', str(legacy))
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(destination))
    with pytest.raises(RuntimeError, match='export/import'):
        validate_legacy_migration()
    SemanticCollection('voice_calls', destination)
    with pytest.raises(RuntimeError, match='export/import'):
        validate_legacy_migration()
    destination.unlink()
    import_export(exported, destination)
    validate_legacy_migration()
    assert (legacy / 'chroma.sqlite3').read_bytes() == b'untouched legacy data'


async def test_private_startup_does_not_silently_ignore_legacy_index(monkeypatch, tmp_path):
    import main as application

    legacy = tmp_path / 'chroma_db'
    legacy.mkdir()
    (legacy / 'chroma.sqlite3').write_bytes(b'original legacy bytes')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.delenv('CHROMA_PERSIST_DIR', raising=False)
    monkeypatch.delenv('SEMANTIC_DB_PATH', raising=False)
    monkeypatch.setattr(application, 'demo_enabled', lambda: False)
    with pytest.raises(RuntimeError, match='export/import'):
        async with application.lifespan(application.app):
            pytest.fail('Unmigrated legacy index must block startup')
    assert (legacy / 'chroma.sqlite3').read_bytes() == b'original legacy bytes'


def test_failed_embedding_never_publishes_partial_import(exported, tmp_path):
    destination = tmp_path / 'new-index.sqlite'
    with patch('storage.semantic_index.embed', side_effect=RuntimeError('synthetic outage')):
        assert main(['import', str(exported), str(destination)]) == 1
    assert not destination.exists()
    assert not list(tmp_path.glob('.semantic-import-*'))


def test_export_size_is_bounded_before_parsing(exported, monkeypatch, tmp_path):
    monkeypatch.setattr('tools.semantic_migration.MAX_EXPORT_BYTES', 1)
    assert main(['import', str(exported), str(tmp_path / 'index.sqlite')]) == 1
    assert not (tmp_path / 'index.sqlite').exists()


@pytest.mark.parametrize('data', [None, {}, {'format': 'wrong', 'collections': {}},
    {'format': 'voicescope-semantic-export-v1', 'collections': {'unrecognized': {}}},
    {'format': 'voicescope-semantic-export-v1', 'collections': {'voice_calls': []}}])
def test_malformed_export_is_not_accepted(tmp_path, data):
    source = tmp_path / 'malformed.json'
    source.write_text(json.dumps(data))
    assert main(['import', str(source), str(tmp_path / 'index.sqlite')]) == 1
    assert not (tmp_path / 'index.sqlite').exists()


def test_legacy_export_requires_explicit_offline_confirmation(tmp_path):
    assert main(['export', str(tmp_path), str(tmp_path / 'export.json')]) == 1
    assert not (tmp_path / 'export.json').exists()


def test_legacy_sdk_only_opens_a_copy_and_original_files_are_unchanged(tmp_path):
    source = tmp_path / 'legacy'
    source.mkdir()
    original = source / 'synthetic-index'
    original.write_bytes(b'preserve legacy index')
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    collection = SimpleNamespace(name='voice_calls', get=lambda **kwargs: {
        'ids': ['id'], 'documents': ['synthetic'], 'metadatas': [None]})
    client = MagicMock()
    client.list_collections.return_value = [collection]
    client.get_collection.return_value = collection
    def open_copy(*, path, settings):
        from pathlib import Path
        assert Path(path) != source
        (Path(path) / 'synthetic-index').write_bytes(b'migration scratch writes')
        return client
    fake = SimpleNamespace(__version__='1.5.9', PersistentClient=open_copy)
    config = SimpleNamespace(Settings=lambda **kwargs: kwargs)
    with patch.dict('sys.modules', {'chromadb': fake, 'chromadb.config': config}):
        result = export_legacy(source, tmp_path / 'export.json')
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert result['collections']['voice_calls']['metadatas'] == [{}]
    assert (tmp_path / 'export.json').stat().st_mode & 0o777 == 0o600
    client._system.stop.assert_called_once()
