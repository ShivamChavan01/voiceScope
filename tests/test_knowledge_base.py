import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = ""


@pytest.fixture(autouse=True)
def isolated_semantic_index(monkeypatch, tmp_path):
    import numpy as np
    from storage import semantic_index
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path / 'semantic.sqlite'))
    monkeypatch.setenv('KNOWLEDGE_DB_PATH', str(tmp_path / 'knowledge.sqlite'))
    monkeypatch.setattr(semantic_index, 'embed', lambda texts: [np.ones(384, dtype='<f4') for _ in texts])


class TestKnowledgeBase:
    def test_missing_file_disables_kb(self):
        from core.knowledge_base import KnowledgeBase

        kb = KnowledgeBase(path="/nonexistent/path/policy.md")
        assert kb.available is False

    def test_empty_file_disables_kb(self):
        from core.knowledge_base import KnowledgeBase

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            path = f.name

        try:
            kb = KnowledgeBase(path=path)
            assert kb.available is False
        finally:
            os.unlink(path)

    def test_valid_file_enables_kb(self):
        from core.knowledge_base import KnowledgeBase

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Refund Policy: Refunds are processed within 5 business days.\n\n")
            f.write("Cancellation Policy: Users can cancel anytime without penalty.")
            path = f.name

        try:
            kb = KnowledgeBase(path=path)
            assert kb.available is True
            assert len(kb.chunks) == 2
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_query_when_unavailable(self):
        from core.knowledge_base import KnowledgeBase

        kb = KnowledgeBase(path="/nonexistent/policy.md")
        results = await kb.query("test claim")
        assert results == []
