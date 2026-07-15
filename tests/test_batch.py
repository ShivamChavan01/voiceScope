import os
import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

from unittest.mock import AsyncMock, patch, MagicMock
from core.batch import BatchProcessor, batches, MAX_BATCHES


@pytest.fixture(autouse=True)
def clear_batches():
    batches.clear()
    yield
    batches.clear()


class TestBatchProcessor:
    @pytest.mark.asyncio
    async def test_create_batch(self):
        with patch("core.batch.VoiceScopePipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value={"run_id": "test"})
            mock_pipeline_cls.return_value = mock_pipeline
            processor = BatchProcessor()

            with patch("core.batch.validate_callback_url_async", new_callable=AsyncMock, return_value=True):
                batch_id = await processor.create_batch(
                    files=[(b"audio1", "call1.mp3"), (b"audio2", "call2.mp3")],
                    callback_url="https://example.com/hook",
                    owner_key="key-1",
                )

            assert batch_id in batches
            assert batches[batch_id]["total"] == 2
            assert batches[batch_id]["owner_key"] == "key-1"

    @pytest.mark.asyncio
    async def test_create_batch_invalid_callback(self):
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()

            with patch("core.batch.validate_callback_url_async", new_callable=AsyncMock, return_value=False):
                with pytest.raises(ValueError, match="Invalid callback_url"):
                    await processor.create_batch(
                        files=[(b"audio", "call.mp3")],
                        callback_url="http://evil.com/hook",
                    )

    def test_get_batch_owner_match(self):
        batches["b1"] = {"batch_id": "b1", "owner_key": "key-1"}
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()
        result = processor.get_batch("b1", owner_key="key-1")
        assert result is not None

    def test_get_batch_owner_mismatch(self):
        batches["b1"] = {"batch_id": "b1", "owner_key": "key-1"}
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()
        result = processor.get_batch("b1", owner_key="key-2")
        assert result is None

    def test_get_batch_no_owner_with_key(self):
        batches["b1"] = {"batch_id": "b1", "owner_key": None}
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()
        result = processor.get_batch("b1", owner_key="key-1")
        assert result is None

    def test_get_batch_no_owner_no_key(self):
        batches["b1"] = {"batch_id": "b1", "owner_key": None}
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()
        result = processor.get_batch("b1", owner_key=None)
        assert result is not None

    def test_get_batch_not_found(self):
        with patch("core.batch.VoiceScopePipeline"):
            processor = BatchProcessor()
        result = processor.get_batch("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_max_batches_eviction(self):
        for i in range(MAX_BATCHES):
            batches[f"batch-{i}"] = {
                "batch_id": f"batch-{i}",
                "owner_key": None,
                "status": "completed",
            }

        with patch("core.batch.VoiceScopePipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value={"run_id": "test"})
            mock_pipeline_cls.return_value = mock_pipeline
            processor = BatchProcessor()

            with patch("core.batch.validate_callback_url_async", new_callable=AsyncMock, return_value=True):
                batch_id = await processor.create_batch(files=[(b"audio", "call.mp3")])

            assert len(batches) == MAX_BATCHES
            assert batch_id in batches

    @pytest.mark.asyncio
    async def test_process_batch_success(self):
        with patch("core.batch.VoiceScopePipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value={"run_id": "test-run"})
            mock_pipeline_cls.return_value = mock_pipeline
            processor = BatchProcessor()

            batches["test-batch"] = {
                "batch_id": "test-batch",
                "status": "processing",
                "total": 1,
                "completed": 0,
                "failed": 0,
                "results": [],
                "callback_url": None,
                "owner_key": None,
            }

            await processor._process_batch("test-batch", [(b"audio", "call.mp3")])

            assert batches["test-batch"]["status"] == "completed"
            assert batches["test-batch"]["completed"] == 1

    @pytest.mark.asyncio
    async def test_process_batch_failure(self):
        with patch("core.batch.VoiceScopePipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(side_effect=Exception("pipeline error"))
            mock_pipeline_cls.return_value = mock_pipeline
            processor = BatchProcessor()

            batches["test-batch"] = {
                "batch_id": "test-batch",
                "status": "processing",
                "total": 1,
                "completed": 0,
                "failed": 0,
                "results": [],
                "callback_url": None,
                "owner_key": None,
            }

            await processor._process_batch("test-batch", [(b"audio", "call.mp3")])

            assert batches["test-batch"]["status"] == "completed"
            assert batches["test-batch"]["failed"] == 1
