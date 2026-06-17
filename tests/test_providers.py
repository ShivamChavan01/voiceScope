import pytest
from llm_providers.base import CompletionResult
from llm_providers.registry import ProviderRegistry


class TestCompletionResult:
    def test_creation(self):
        result = CompletionResult(
            content="test",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )
        assert result.content == "test"
        assert result.model == "gpt-4o"
        assert result.provider == "openai"
        assert result.cost_usd == 0.001


class TestProviderRegistry:
    def test_list_providers(self):
        providers = ProviderRegistry.list_providers()
        assert isinstance(providers, list)

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderRegistry.get("nonexistent_provider")
