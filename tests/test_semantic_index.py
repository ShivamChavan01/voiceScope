"""Local semantic storage contracts, independent of any paid provider."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import numpy as np
import pytest

from storage import semantic_index as index


@pytest.fixture
def collection(monkeypatch, tmp_path):
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path / 'semantic' / 'index.sqlite'))
    def vectors(texts):
        result = []
        for text in texts:
            vector = np.zeros(index.DIMENSIONS, dtype='<f4')
            vector[0 if 'refund' in text else 1] = 1
            result.append(vector)
        return result
    monkeypatch.setattr(index, 'embed', vectors)
    return index.SemanticCollection('policies')


def test_semantic_ranking_persistence_metadata_and_private_permissions(collection):
    collection.upsert(ids=['delivery', 'refund'], documents=['delivery guidance', 'refund guidance'], metadatas=[{}, {'version': 'v1'}])
    reopened = index.SemanticCollection('policies')
    assert reopened.query(query_texts=['refund please'], n_results=1)['documents'] == [['refund guidance']]
    assert reopened.get()['metadatas'] == [{}, {'version': 'v1'}]
    assert reopened.path.stat().st_mode & 0o777 == 0o600


def test_collections_and_ids_are_isolated_and_duplicates_are_upserts(collection):
    other = index.SemanticCollection('calls')
    collection.upsert(ids=['same'], documents=['refund original'])
    other.upsert(ids=['same'], documents=['delivery call'])
    collection.upsert(ids=['same'], documents=['refund updated'])
    assert collection.count() == 1
    assert other.get()['documents'] == ['delivery call']
    collection.delete(ids=['same'])
    assert collection.count() == 0
    assert other.count() == 1


def test_replace_is_atomic_and_empty_sources_remove_stale_knowledge(collection):
    collection.upsert(ids=['old'], documents=['refund old'])
    with patch.object(index, 'embed', side_effect=RuntimeError('synthetic embedding outage')):
        with pytest.raises(RuntimeError):
            collection.replace(ids=['new'], documents=['new guidance'])
    assert collection.get()['documents'] == ['refund old']
    collection.replace(ids=['new'], documents=['delivery new'])
    assert collection.get()['ids'] == ['new']
    collection.replace(ids=[], documents=[])
    assert collection.query(query_texts=['refund']) == {'documents': [[]]}


@pytest.mark.parametrize('ids,documents,metadata', [
    (['x', 'x'], ['a', 'b'], None), (['x'], [], None), ([''], ['a'], None),
    (['x'], [' '], None), (['x'], ['a'], []), (['x'], ['a'], [None]),
    (['x'], ['a'], [{'number': float('nan')}]),
])
def test_invalid_writes_preserve_previous_data(collection, ids, documents, metadata):
    collection.upsert(ids=['original'], documents=['refund guidance'])
    with pytest.raises(ValueError):
        collection.replace(ids=ids, documents=documents, metadatas=metadata)
    assert collection.get()['ids'] == ['original']


@pytest.mark.parametrize('limit', [0, -1, 201, True, 1.5])
def test_query_limit_is_bounded(collection, limit):
    with pytest.raises(ValueError):
        collection.query(query_texts=['refund'], n_results=limit)


def test_concurrent_writes_and_deterministic_ties(collection):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: collection.upsert(ids=[str(i)], documents=[f'refund {i}']), range(8)))
    assert collection.count() == 8
    assert collection.query(query_texts=['refund'], n_results=2)['documents'] == [['refund 0', 'refund 1']]


def test_model_mismatch_is_not_silently_compared(collection):
    collection.upsert(ids=['x'], documents=['refund'])
    with sqlite3.connect(collection.path) as conn:
        conn.execute("UPDATE semantic_documents SET model='unverified-model'")
    with pytest.raises(ValueError, match='reindex'):
        collection.query(query_texts=['refund'])


@pytest.mark.parametrize('vectors', [[], [np.zeros(384)], [np.ones(383)],
    [np.full(384, np.nan)], [np.full(384, np.inf)]])
def test_embedding_outputs_require_matching_finite_nonzero_vectors(monkeypatch, vectors):
    from types import SimpleNamespace
    monkeypatch.setattr(index, 'embedding_model', lambda: SimpleNamespace(embed=lambda texts: vectors))
    with pytest.raises(ValueError):
        index.embed(['synthetic'])


def test_embedding_vectors_are_normalized_without_float32_overflow(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(index, 'embedding_model', lambda: SimpleNamespace(embed=lambda texts: [np.full(384, 1e30)]))
    result = index.embed(['synthetic'])[0]
    assert np.isfinite(result).all()
    assert np.linalg.norm(result) == pytest.approx(1)


def test_fixed_model_constructor_has_no_data_or_remote_code_options(monkeypatch):
    from unittest.mock import MagicMock
    model = MagicMock()
    monkeypatch.setattr(index, 'TextEmbedding', model)
    monkeypatch.setenv('CHROMA_API_IMPL', 'untrusted.server')
    index.embedding_model.cache_clear()
    try:
        index.embedding_model()
        assert model.call_args.kwargs['model_name'] == index.MODEL_NAME
        assert 'trust_remote_code' not in model.call_args.kwargs
    finally:
        index.embedding_model.cache_clear()
