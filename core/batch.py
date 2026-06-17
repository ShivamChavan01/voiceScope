import asyncio
import uuid
import httpx
from datetime import datetime, timezone
from core.pipeline import VoiceScopePipeline
from utils.logger import logger
from typing import Optional


batches: dict[str, dict] = {}


class BatchProcessor:
    def __init__(self):
        self.pipeline = VoiceScopePipeline()

    async def create_batch(
        self,
        files: list[tuple[bytes, str]],
        callback_url: Optional[str] = None,
    ) -> str:
        batch_id = str(uuid.uuid4())
        batches[batch_id] = {
            "batch_id": batch_id,
            "status": "processing",
            "total": len(files),
            "completed": 0,
            "failed": 0,
            "results": [],
            "callback_url": callback_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        asyncio.create_task(self._process_batch(batch_id, files))
        return batch_id

    async def _process_batch(self, batch_id: str, files: list[tuple[bytes, str]]):
        batch = batches[batch_id]

        for audio_bytes, filename in files:
            try:
                result = await self.pipeline.run(audio_bytes, filename)
                batch["results"].append(result)
                batch["completed"] += 1
            except Exception as e:
                batch["results"].append({"filename": filename, "error": str(e)})
                batch["failed"] += 1
                logger.error(f"[BatchProcessor] batch={batch_id} file={filename} error={e}")

        batch["status"] = "completed"
        batch["completed_at"] = datetime.now(timezone.utc).isoformat()

        if batch["callback_url"]:
            await self._send_callback(batch)

    async def _send_callback(self, batch: dict):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(batch["callback_url"], json=batch)
                logger.info(f"[BatchProcessor] callback sent batch={batch['batch_id']}")
        except Exception as e:
            logger.error(f"[BatchProcessor] callback failed batch={batch['batch_id']} error={e}")

    def get_batch(self, batch_id: str) -> Optional[dict]:
        return batches.get(batch_id)
