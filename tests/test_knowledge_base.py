import os
import pytest
import tempfile

os.environ["DATABASE_URL"] = ""


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
