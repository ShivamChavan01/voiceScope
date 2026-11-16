import asyncio
from functools import partial

from storage.semantic_index import SemanticCollection

from utils.logger import logger


class TranscriptStore:
    """
    Persistent local semantic store for voice call transcripts.
    Used by AnalysisAgent (RAG retrieval) and ReportAgent (storage).
    """

    def __init__(self):
        try:
            self.collection = SemanticCollection('voice_calls')
            logger.info('[TranscriptStore] initialized — collection=voice_calls')
        except Exception as e:
            logger.warning(f"[TranscriptStore] init failed (non-critical): {type(e).__name__}")
            self.collection = None

    async def store(self, doc_id: str, text: str, metadata: dict | None = None):
        """Store a transcript for future RAG retrieval."""
        if self.collection is None:
            return
        if metadata is None:
            metadata = {}
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                partial(self.collection.upsert, ids=[doc_id], documents=[text], metadatas=[metadata]),
            )
            logger.info(f"[TranscriptStore] stored doc_id={doc_id}")
        except Exception as e:
            logger.warning(f"[TranscriptStore] store failed (non-critical): {type(e).__name__}")

    async def query(self, text: str, n_results: int = 3) -> list[str]:
        """Retrieve similar past transcripts."""
        if self.collection is None:
            return []
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, partial(self.collection.query, query_texts=[text], n_results=n_results)
            )
            docs: list[str] = results.get("documents", [[]])[0]
            logger.info(f"[TranscriptStore] query returned {len(docs)} results")
            return docs
        except Exception as e:
            logger.warning(f"[TranscriptStore] query failed (non-critical): {type(e).__name__}")
            return []
