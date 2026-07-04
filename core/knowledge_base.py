import chromadb
from pathlib import Path
from utils.logger import logger
import os
import asyncio
from functools import partial


class KnowledgeBase:
    """
    Policy knowledge base stored in ChromaDB.
    Used by AnalysisAgent for grounded hallucination detection.
    Chunks a markdown/text policy file into paragraphs and enables semantic search.
    """

    def __init__(self, path: str = "knowledge/business_policy.md"):
        self.available = False
        self.collection = None

        file_path = Path(path)
        if not file_path.exists():
            logger.warning(f"[KnowledgeBase] policy file not found: {path} — KB disabled")
            return

        try:
            raw = file_path.read_text(encoding="utf-8")
            self.chunks = [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]

            if not self.chunks:
                logger.warning(f"[KnowledgeBase] policy file empty: {path}")
                return

            persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/tmp/chroma_db")
            client = chromadb.PersistentClient(path=persist_dir)
            self.collection = client.get_or_create_collection(
                name="policy_kb", metadata={"hnsw:space": "cosine"}
            )

            ids = [f"policy_{i}" for i in range(len(self.chunks))]
            self.collection.upsert(
                ids=ids,
                documents=self.chunks,
                metadatas=[{"chunk_index": i} for i in range(len(self.chunks))],
            )

            self.available = True
            logger.info(f"[KnowledgeBase] loaded {len(self.chunks)} chunks from {path}")

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
