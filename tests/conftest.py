import pytest
from unittest.mock import AsyncMock
from llm_providers.base import CompletionResult


@pytest.fixture
def mock_completion_result():
    return CompletionResult(
        content='{"intent": "test", "sentiment_arc": "neutral", "hallucination_detected": false, "outcome": "resolved", "escalation_signal": false}',
        model="gpt-4o",
        provider="openai",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
    )


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.name = "openai"
    provider.default_model = "gpt-4o"
    provider.complete = AsyncMock(
        return_value=CompletionResult(
            content='{"intent": "test intent", "sentiment_arc": "neutral", "hallucination_detected": false, "outcome": "resolved", "escalation_signal": false}',
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )
    )
    return provider


@pytest.fixture
def sample_audio_bytes():
    return b"fake audio data for testing"
