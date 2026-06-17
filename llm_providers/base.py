from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional


class CompletionResult(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class LLMProvider(ABC):
    name: str
    default_model: str

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[dict] = None,
    ) -> CompletionResult: ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float: ...
