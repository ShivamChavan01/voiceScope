"""Real embedded index reconciliation, with deterministic local embeddings."""
import pytest
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from core.knowledge_base import KnowledgeBase


@pytest.fixture
def knowledge(monkeypatch, tmp_path):
    monkeypatch.setenv('KNOWLEDGE_DB_PATH', str(tmp_path / 'knowledge.db'))
    monkeypatch.setenv('CHROMA_PERSIST_DIR', str(tmp_path / 'chroma'))
    monkeypatch.setattr(DefaultEmbeddingFunction, '__call__', lambda self, input: [[1.0, 0.0] for _ in input])
    path = tmp_path / 'policy.md'
    path.write_text('Synthetic current guidance.\n\nSynthetic retired guidance.')
    return KnowledgeBase(str(path)), path


def test_removed_knowledge_is_absent_after_reload(knowledge):
    kb, path = knowledge
    assert kb.available
    assert kb.collection.count() == 2
    path.write_text('Synthetic current guidance.')
    kb.reload()
    assert kb.available
    assert kb.collection.get()['documents'] == ['Synthetic current guidance.']


def test_empty_knowledge_clears_index_and_can_be_reenabled(knowledge):
    kb, path = knowledge
    path.write_text('')
    kb.reload()
    assert not kb.available
    assert kb.collection.count() == 0
    path.write_text('Synthetic replacement guidance.')
    kb.reload()
    assert kb.available
    assert kb.collection.get()['documents'] == ['Synthetic replacement guidance.']


async def test_failed_upsert_retains_previous_index(knowledge, monkeypatch):
    kb, path = knowledge
    previous = kb.collection.get()['documents']
    def fail(self, **kwargs):
        raise RuntimeError('Synthetic index write failure')
    monkeypatch.setattr(type(kb.collection), 'upsert', fail)
    path.write_text('Synthetic replacement guidance.')
    kb.reload()
    assert not kb.available
    assert kb.collection.get()['documents'] == previous
