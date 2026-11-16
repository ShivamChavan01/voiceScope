import asyncio
from functools import partial
from pathlib import Path
from typing import Any

from core.knowledge_store import KnowledgeStore
from storage.semantic_index import SemanticCollection
from utils.logger import logger


class KnowledgeBase:
    """
    Policy knowledge base stored in a local semantic index.
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
        self.reload()

    def _file_chunks(self) -> list[str]:
        file_path = Path(self.path)
        if not file_path.exists():
            logger.warning(f"[KnowledgeBase] policy file not found: {self.path}")
            return []
        raw = file_path.read_text(encoding="utf-8")
        return [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]

    def reload(self) -> None:
        """Atomically rebuild the semantic index from file and user entries."""
        try:
            file_chunks = self._file_chunks()
            user_chunks = self.store.get_chunks()
            self.chunks = file_chunks + user_chunks

            self.collection = SemanticCollection('policy_kb')

            ids = [f"policy_{i}" for i in range(len(self.chunks))]
            self.collection.replace(ids=ids, documents=self.chunks,
                metadatas=[{"chunk_index": i} for i in range(len(self.chunks))])

            self.available = bool(self.chunks)
            logger.info(
                f"[KnowledgeBase] loaded {len(file_chunks)} file + "
                f"{len(user_chunks)} user chunks from {self.path}"
            )

        except Exception as e:
            logger.error(f"[KnowledgeBase] initialization failed: {type(e).__name__}")
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
            logger.debug(f"[KnowledgeBase] query returned {len(docs)} results")
            return docs

        except Exception as e:
            logger.warning(f"[KnowledgeBase] query failed: {type(e).__name__}")
            return []
