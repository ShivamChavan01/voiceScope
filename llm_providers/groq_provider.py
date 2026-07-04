from openai import AsyncOpenAI
from llm_providers.base import LLMProvider, CompletionResult
from typing import Optional
import os


GROQ_PRICING = {
    "llama3-70b-8192": {"input": 0.0, "output": 0.0},
    "llama3-8b-8192": {"input": 0.0, "output": 0.0},
    "mixtral-8x7b-32768": {"input": 0.0, "output": 0.0},
    "gemma-7b-it": {"input": 0.0, "output": 0.0},
}


class GroqProvider(LLMProvider):
    name = "groq"
    default_model = "llama3-70b-8192"

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
