import chromadb
from utils.logger import logger
import os
import asyncio
from functools import partial


class ChromaStore:
    """
    Persistent ChromaDB store for voice call transcripts.
    Used by AnalysisAgent (RAG retrieval) and ReportAgent (storage).
    """

    def __init__(self):
        data_dir = os.environ.get("DATA_DIR", "/tmp")
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", os.path.join(data_dir, "chroma_db"))
        try:
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(
                name="voice_calls", metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"[ChromaStore] initialized — collection=voice_calls, path={persist_dir}")
        except Exception as e:
            logger.warning(f"[ChromaStore] init failed (non-critical): {e}")
            self.client = None
            self.collection = None

    async def store(self, doc_id: str, text: str, metadata: dict = {}):
        """Store a transcript for future RAG retrieval."""
        if not self.collection:
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(self.collection.upsert, ids=[doc_id], documents=[text], metadatas=[metadata]),
            )
            logger.info(f"[ChromaStore] stored doc_id={doc_id}")
        except Exception as e:
            logger.warning(f"[ChromaStore] store failed (non-critical): {e}")

    async def query(self, text: str, n_results: int = 3) -> list[str]:
        """Retrieve similar past transcripts."""
        if not self.collection:
            return []
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, partial(self.collection.query, query_texts=[text], n_results=n_results)
            )
            docs: list[str] = results.get("documents", [[]])[0]
            logger.info(f"[ChromaStore] query returned {len(docs)} results")
            return docs
        except Exception as e:
            logger.warning(f"[ChromaStore] query failed (non-critical): {e}")
            return []
