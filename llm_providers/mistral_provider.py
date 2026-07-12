from mistralai import MistralAsyncClient
from llm_providers.base import LLMProvider, CompletionResult
from typing import Optional
import os


MISTRAL_PRICING = {
    "mistral-large-latest": {"input": 2.00, "output": 6.00},
    "mistral-medium-latest": {"input": 2.70, "output": 8.10},
    "mistral-small-latest": {"input": 0.20, "output": 0.60},
    "open-mixtral-8x7b": {"input": 0.60, "output": 0.60},
}


class MistralProvider(LLMProvider):
    name = "mistral"
    default_model = "mistral-large-latest"

    def __init__(self):
        self.client = MistralAsyncClient(api_key=os.getenv("MISTRAL_API_KEY"))

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[dict] = None,
    ) -> CompletionResult:
        model = model or self.default_model
        response = await self.client.chat.complete_async(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return CompletionResult(
            content=content,
            model=model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = MISTRAL_PRICING.get(model, MISTRAL_PRICING["mistral-large-latest"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
