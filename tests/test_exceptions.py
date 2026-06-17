import pytest
from utils.exceptions import (
    VoiceScopeError,
    TranscriptionError,
    AnalysisError,
    ProviderError,
    RateLimitError,
    CircuitBreakerOpenError,
)


class TestExceptions:
    def test_voice_scope_error(self):
        with pytest.raises(VoiceScopeError):
            raise VoiceScopeError("test")

    def test_transcription_error(self):
        with pytest.raises(TranscriptionError):
            raise TranscriptionError("test")

    def test_provider_error_includes_provider(self):
        with pytest.raises(ProviderError) as exc_info:
            raise ProviderError("openai", "rate limited")
        assert exc_info.value.provider == "openai"
        assert "[openai]" in str(exc_info.value)

    def test_rate_limit_error(self):
        with pytest.raises(RateLimitError):
            raise RateLimitError("anthropic")

    def test_circuit_breaker_error(self):
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            raise CircuitBreakerOpenError("gemini")
        assert exc_info.value.service == "gemini"
