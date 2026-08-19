import os
from typing import Optional

from openai import AsyncOpenAI

from llm_providers.base import CompletionResult, LLMProvider

GROQ_PRICING = {
    "openai/gpt-oss-120b": {"input": 0.0, "output": 0.0},
    "openai/gpt-oss-20b": {"input": 0.0, "output": 0.0},
    "qwen/qwen3.6-27b": {"input": 0.0, "output": 0.0},
    "allam-2-7b": {"input": 0.0, "output": 0.0},
}


class GroqProvider(LLMProvider):
    name = "groq"
    default_model = "openai/gpt-oss-120b"

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
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
            cost_usd=0.0,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        return 0.0
