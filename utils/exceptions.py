class VoiceScopeError(Exception):
    pass


class TranscriptionError(VoiceScopeError):
    pass


class AnalysisError(VoiceScopeError):
    pass


class ReportError(VoiceScopeError):
    pass


class ProviderError(VoiceScopeError):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    def __init__(self, provider: str):
        super().__init__(provider, "Rate limit exceeded")


class CircuitBreakerOpenError(VoiceScopeError):
    def __init__(self, service: str):
        self.service = service
        super().__init__(f"Circuit breaker open for {service}")
