import asyncio
import os
from functools import partial
from pathlib import Path
from typing import Any

import chromadb

from core.knowledge_store import KnowledgeStore
from utils.logger import logger


class KnowledgeBase:
    """
    Policy knowledge base stored in ChromaDB.
    Used by AnalysisAgent for grounded hallucination detection.

    Sources (merged, in order):
      1. The static `knowledge/business_policy.md` file (default seed)
      2. User-added entries from KnowledgeStore (editable via API / Settings)

    Chunks each policy paragraph and enables semantic search.
    """

    def __init__(self, path: str = "knowledge/business_policy.md"):
        self.path = path
        self.store = KnowledgeStore()
        self.available = False
        self.collection: Any = None
        self.chunks: list[str] = []
        self._client: Any = None
        self.reload()

    def _file_chunks(self) -> list[str]:
        file_path = Path(self.path)
        if not file_path.exists():
            logger.warning(f"[KnowledgeBase] policy file not found: {self.path}")
            return []
        raw = file_path.read_text(encoding="utf-8")
        return [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]

    def reload(self) -> None:
        """Rebuild the ChromaDB index from the file plus user-added entries."""
        try:
            file_chunks = self._file_chunks()
            user_chunks = self.store.get_chunks()
            self.chunks = file_chunks + user_chunks

            if not self.chunks:
                logger.warning("[KnowledgeBase] no policy chunks — KB disabled")
                self.available = False
                return

            persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/tmp/chroma_db")
            self._client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self._client.get_or_create_collection(
                name="policy_kb", metadata={"hnsw:space": "cosine"}
            )

            ids = [f"policy_{i}" for i in range(len(self.chunks))]
            self.collection.upsert(
                ids=ids,
                documents=self.chunks,
                metadatas=[{"chunk_index": i} for i in range(len(self.chunks))],
            )

            self.available = True
            logger.info(
                f"[KnowledgeBase] loaded {len(file_chunks)} file + "
                f"{len(user_chunks)} user chunks from {self.path}"
            )

        except Exception as e:
            logger.error(f"[KnowledgeBase] initialization failed: {e}")
            self.available = False

    async def query(self, claim: str, n_results: int = 3) -> list[str]:
        if not self.available or not self.collection:
            return []

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                partial(
                    self.collection.query,
                    query_texts=[claim],
                    n_results=n_results,
                ),
            )
            docs_data = results.get("documents", [[]])
            docs: list[str] = docs_data[0] if docs_data else []
            logger.debug(f"[KnowledgeBase] query returned {len(docs)} results for '{claim[:50]}'")
            return docs

        except Exception as e:
            logger.warning(f"[KnowledgeBase] query failed: {e}")
            return []
