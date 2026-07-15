import os
import pytest

os.environ["DATABASE_URL"] = ""

from unittest.mock import AsyncMock, MagicMock, patch
from storage.chroma_store import ChromaStore


class TestChromaStore:
    def test_init_failure_sets_none(self):
        with patch("chromadb.PersistentClient", side_effect=Exception("ChromaDB error")):
            store = ChromaStore()
            assert store.client is None
            assert store.collection is None

    @pytest.mark.asyncio
    async def test_store_when_collection_none(self):
        with patch("chromadb.PersistentClient", side_effect=Exception("init fail")):
            store = ChromaStore()
            await store.store("doc1", "text1")
            # Should not raise

    @pytest.mark.asyncio
    async def test_query_when_collection_none(self):
        with patch("chromadb.PersistentClient", side_effect=Exception("init fail")):
            store = ChromaStore()
            result = await store.query("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_store_with_mocked_collection(self):
        mock_collection = MagicMock()
        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            store = ChromaStore()
            await store.store("doc1", "transcript text", {"outcome": "resolved"})
            mock_collection.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_mocked_collection(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"documents": [["result1", "result2"]]}
        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            store = ChromaStore()
            result = await store.query("test transcript", n_results=2)
            assert result == ["result1", "result2"]

    @pytest.mark.asyncio
    async def test_store_exception_handled(self):
        mock_collection = MagicMock()
        mock_collection.upsert.side_effect = Exception("write error")
        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            store = ChromaStore()
            await store.store("doc1", "text")  # Should not raise

    @pytest.mark.asyncio
    async def test_query_exception_handled(self):
        mock_collection = MagicMock()
        mock_collection.query.side_effect = Exception("query error")
        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            store = ChromaStore()
            result = await store.query("test")
            assert result == []
