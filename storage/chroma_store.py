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
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/tmp/chroma_db")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="voice_calls", metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"[ChromaStore] initialized — collection=voice_calls, path={persist_dir}")

    async def store(self, doc_id: str, text: str, metadata: dict = {}):
        """Store a transcript for future RAG retrieval."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.collection.upsert, ids=[doc_id], documents=[text], metadatas=[metadata]),
        )
        logger.info(f"[ChromaStore] stored doc_id={doc_id}")

    async def query(self, text: str, n_results: int = 3) -> list[str]:
        """Retrieve similar past transcripts."""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, partial(self.collection.query, query_texts=[text], n_results=n_results)
        )
        docs: list[str] = results.get("documents", [[]])[0]
        logger.info(f"[ChromaStore] query returned {len(docs)} results")
        return docs
