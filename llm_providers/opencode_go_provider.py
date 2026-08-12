from openai import AsyncOpenAI
from llm_providers.base import LLMProvider, CompletionResult
from typing import Optional
import os


OPENCODE_GO_PRICING = {
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.6-luna-max": {"input": 0.20, "output": 1.20},
    "deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "deepseek-v4-pro": {"input": 0.435, "output": 0.87},
    "mimo-v2.5": {"input": 0.14, "output": 0.28},
    "hy3": {"input": 0.14, "output": 0.58},
    "qwen3.7-plus": {"input": 0.40, "output": 1.60},
}


class OpenCodeGoProvider(LLMProvider):
    name = "opencode-go"
    default_model = "gpt-5.6-luna"

    def __init__(self):
        self.base_url = os.getenv(
            "OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1"
        )
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENCODE_GO_API_KEY"),
            base_url=self.base_url,
            timeout=90.0,
        )

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[dict] = None,
    ) -> CompletionResult:
        model = model or os.getenv("LLM_MODEL", self.default_model)

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
        pricing = OPENCODE_GO_PRICING.get(model, {"input": 0.0, "output": 0.0})
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
