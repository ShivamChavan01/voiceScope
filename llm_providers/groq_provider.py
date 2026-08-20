import os
from typing import Optional

from openai import AsyncOpenAI

from llm_providers.base import CompletionResult, LLMProvider
from utils.logger import logger

GROQ_PRICING = {
    "openai/gpt-oss-120b": {"input": 0.0, "output": 0.0},
    "openai/gpt-oss-20b": {"input": 0.0, "output": 0.0},
    "qwen/qwen3.6-27b": {"input": 0.0, "output": 0.0},
    "allam-2-7b": {"input": 0.0, "output": 0.0},
}


def _is_json_validation_error(exc: Exception) -> bool:
    text = str(exc)
    return "json_validate_failed" in text or "Failed to generate JSON" in text


class GroqProvider(LLMProvider):
    name = "groq"
    default_model = "openai/gpt-oss-120b"
    required_env = ("GROQ_API_KEY",)

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

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Strict JSON validation (json_object / json_schema) on some open
            # models fails when the model emits empty/output — retry WITHOUT the
            # response_format constraint; the prompt already asks for JSON.
            if response_format and _is_json_validation_error(exc):
                logger.warning(
                    f"[GroqProvider] json_validate_failed on {model} — retrying without"
                    f" response_format"
                )
                kwargs.pop("response_format", None)
                response = await self.client.chat.completions.create(**kwargs)
            else:
                raise

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
