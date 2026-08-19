import os
from typing import Optional

from openai import AsyncOpenAI

from llm_providers.base import CompletionResult, LLMProvider


class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            timeout=90.0,
        )

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

        if not response.choices:
            raise ValueError("LLM returned no choices")

        choice = response.choices[0]
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return CompletionResult(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        if model.endswith(":free"):
            return 0.0
        return 0.0