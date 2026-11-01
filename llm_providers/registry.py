import os
from typing import Optional

from llm_providers.base import CompletionResult, LLMProvider
from utils.logger import logger
from utils.resilience import CircuitBreaker, CircuitBreakerOpenError


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
        from core.staging import require_live_services
        require_live_services()
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
    def _backup_names(cls, primary: str) -> list[str]:
        """Ordered fallback providers from LLM_BACKUP_PROVIDERS (comma-separated),
        restricted to those that are either already instantiated or have their
        credentials configured."""
        raw = os.getenv("LLM_BACKUP_PROVIDERS", "")
        names = [b.strip() for b in raw.split(",") if b.strip() and b.strip() != primary]
        configured = []
        for backend in names:
            provider_cls = cls._providers.get(backend)
            if provider_cls is None:
                continue
            if backend not in cls._instances and not provider_cls.is_configured():
                logger.warning(
                    f"[ProviderRegistry] skipping backup '{backend}' — missing "
                    f"credentials {provider_cls.required_env}"
                )
                continue
            configured.append(backend)
        return configured

    @classmethod
    async def call(cls, name: Optional[str] = None, **complete_kwargs) -> CompletionResult:
        """Call a provider with circuit breaker protection and ordered fallback.

        The primary provider comes from `name` (or LLM_PROVIDER). If it fails
        (rate limit, quota, outage, open circuit), the request falls through to
        each provider listed in LLM_BACKUP_PROVIDERS.
        """
        from core.staging import require_live_services
        require_live_services()
        name = name or os.getenv("LLM_PROVIDER", "openai")
        assert name is not None

        backends = [name] + cls._backup_names(name)
        last_exc: Optional[Exception] = None
        for backend in backends:
            provider_cls = cls._providers.get(backend)
            if provider_cls is None:
                last_exc = ValueError(f"Unknown provider '{backend}'")
                continue

            # Use an already-instantiated provider if available (tests inject
            # mocks here); otherwise check credentials before instantiating.
            provider = cls._instances.get(backend)
            if provider is None:
                if not provider_cls.is_configured():
                    exc = ValueError(
                        f"Provider '{backend}' not configured — missing {provider_cls.required_env}"
                    )
                    logger.warning(f"[ProviderRegistry] skipping '{backend}': {type(exc).__name__}")
                    last_exc = exc
                    continue

                cb = cls._circuit_breakers.get(backend)
                if cb and cb.is_open():
                    last_exc = CircuitBreakerOpenError(f"Circuit breaker open for provider '{backend}'")
                    logger.warning(f"[ProviderRegistry] failover '{backend}': {type(last_exc).__name__}")
                    continue

                try:
                    provider = cls.get(backend)
                except Exception as exc:
                    if cb:
                        cb.record_failure()
                    logger.warning(f"[ProviderRegistry] init '{backend}' failed: {type(exc).__name__}")
                    last_exc = exc
                    continue
            else:
                cb = cls._circuit_breakers.get(backend)
                if cb and cb.is_open():
                    last_exc = CircuitBreakerOpenError(f"Circuit breaker open for provider '{backend}'")
                    logger.warning(f"[ProviderRegistry] failover '{backend}': {type(last_exc).__name__}")
                    continue

            try:
                result = await provider.complete(**complete_kwargs)
                if cb:
                    cb.record_success()
                if backend != name:
                    logger.info(f"[ProviderRegistry] failover used provider={backend}")
                return result
            except Exception as exc:
                if cb:
                    cb.record_failure()
                if backend != name:
                    logger.warning(f"[ProviderRegistry] failover '{backend}' failed: {type(exc).__name__}")
                last_exc = exc

        assert last_exc is not None
        raise last_exc

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

    try:
        from llm_providers.opencode_go_provider import OpenCodeGoProvider

        ProviderRegistry.register(OpenCodeGoProvider)
    except ImportError:
        pass

    try:
        from llm_providers.openrouter_provider import OpenRouterProvider

        ProviderRegistry.register(OpenRouterProvider)
    except ImportError:
        pass


_register_all()
