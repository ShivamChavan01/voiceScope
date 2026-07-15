from openai import AsyncOpenAI
from llm_providers.base import LLMProvider, CompletionResult
from typing import Optional
import os


OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


class OpenAIProvider(LLMProvider):
    name = "openai"
    default_model = "gpt-4o"

    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60.0)

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[dict] = None,
    ) -> CompletionResult:
        model = model or self.default_model
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        if not response.choices:
            raise ValueError("LLM returned no choices")

        return CompletionResult(
            content=response.choices[0].message.content or "",
            model=model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = OPENAI_PRICING.get(model, OPENAI_PRICING["gpt-4o"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
