import pytest
import os
from storage.cost_store import CostStore


@pytest.fixture
def cost_store(tmp_path):
    os.environ["COST_DB_PATH"] = str(tmp_path / "test_costs.db")
    return CostStore()


class TestCostStore:
    @pytest.mark.asyncio
    async def test_log_cost(self, cost_store):
        await cost_store.log_cost(
            run_id="test-123",
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )
        summary = await cost_store.get_summary()
        assert summary["overall"]["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_get_summary_empty(self, cost_store):
        summary = await cost_store.get_summary()
        assert summary["overall"]["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_cost_by_provider(self, cost_store):
        await cost_store.log_cost("r1", "openai", "gpt-4o", 100, 50, 0.001)
        await cost_store.log_cost("r2", "anthropic", "claude-3", 200, 100, 0.002)
        summary = await cost_store.get_summary()
        assert "openai" in summary["by_provider"]
        assert "anthropic" in summary["by_provider"]
