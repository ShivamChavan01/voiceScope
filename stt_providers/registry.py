from stt_providers.base import STTProvider
from utils.logger import logger
from typing import Optional
import os


class STTRegistry:
    _providers: dict[str, type[STTProvider]] = {}
    _instances: dict[str, STTProvider] = {}

    @classmethod
    def register(cls, provider_class: type[STTProvider]):
        cls._providers[provider_class.name] = provider_class
        return provider_class

    @classmethod
    def get(cls, name: Optional[str] = None) -> STTProvider:
        name = name or cls._detect_provider()

        if name in cls._instances:
            return cls._instances[name]

        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown STT provider '{name}'. Available: {available}")

        provider = cls._providers[name]()
        cls._instances[name] = provider
        logger.info(f"[STTRegistry] initialized provider={name}")
        return provider

    @classmethod
    def _detect_provider(cls) -> str:
        explicit = os.getenv("STT_PROVIDER", "").lower()
        if explicit in cls._providers:
            return explicit
        if os.getenv("DEEPGRAM_API_KEY") and "deepgram" in cls._providers:
            return "deepgram"
        if os.getenv("LLM_PROVIDER") == "gemini" or (
            os.getenv("GOOGLE_API_KEY") and not os.getenv("OPENAI_API_KEY")
        ):
            if "gemini" in cls._providers:
                return "gemini"
        return "whisper"

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())


def _register_all():
    try:
        from stt_providers.deepgram_provider import DeepgramProvider
        STTRegistry.register(DeepgramProvider)
    except ImportError:
        pass

    try:
        from stt_providers.whisper_provider import WhisperProvider
        STTRegistry.register(WhisperProvider)
    except ImportError:
        pass

    try:
        from stt_providers.gemini_provider import GeminiSTTProvider
        STTRegistry.register(GeminiSTTProvider)
    except ImportError:
        pass


_register_all()
