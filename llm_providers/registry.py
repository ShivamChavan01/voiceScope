from llm_providers.base import LLMProvider, CompletionResult
from utils.resilience import CircuitBreaker, CircuitBreakerOpenError
from utils.logger import logger
from typing import Optional
import os


class ProviderRegistry:
    _providers: dict[str, type[LLMProvider]] = {}
    _instances: dict[str, LLMProvider] = {}
    _circuit_breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def register(cls, provider_class: type[LLMProvider]):
        cls._providers[provider_class.name] = provider_class
        return provider_class

    @classmethod
    def get(cls, name: Optional[str] = None) -> LLMProvider:
        name = name or os.getenv("LLM_PROVIDER", "openai")

        if name in cls._instances:
            return cls._instances[name]

        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider '{name}'. Available: {available}")

        provider = cls._providers[name]()
        cls._instances[name] = provider
        cls._circuit_breakers[name] = CircuitBreaker()
        logger.info(f"[ProviderRegistry] initialized provider={name}")
        return provider

    @classmethod
    async def call(cls, name: Optional[str] = None, **complete_kwargs) -> CompletionResult:
        """Call a provider with circuit breaker protection."""
        name = name or os.getenv("LLM_PROVIDER", "openai")
        assert name is not None
        cb = cls._circuit_breakers.get(name)

        if cb and cb.is_open():
            raise CircuitBreakerOpenError(f"Circuit breaker open for provider '{name}'")

        provider = cls.get(name)
        try:
            result = await provider.complete(**complete_kwargs)
            if cb:
                cb.record_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception:
            if cb:
                cb.record_failure()
            raise

    @classmethod
    def get_circuit_breaker(cls, name: str) -> Optional[CircuitBreaker]:
        return cls._circuit_breakers.get(name)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())


def _register_all():
    try:
        from llm_providers.openai_provider import OpenAIProvider

        ProviderRegistry.register(OpenAIProvider)
    except ImportError:
        pass

    try:
        from llm_providers.anthropic_provider import AnthropicProvider

        ProviderRegistry.register(AnthropicProvider)
    except ImportError:
        pass

    try:
        from llm_providers.gemini_provider import GeminiProvider

        ProviderRegistry.register(GeminiProvider)
    except ImportError:
        pass

    try:
        from llm_providers.ollama_provider import OllamaProvider

        ProviderRegistry.register(OllamaProvider)
    except ImportError:
        pass

    try:
        from llm_providers.mistral_provider import MistralProvider

        ProviderRegistry.register(MistralProvider)
    except ImportError:
        pass

    try:
        from llm_providers.groq_provider import GroqProvider

        ProviderRegistry.register(GroqProvider)
    except ImportError:
        pass


_register_all()
