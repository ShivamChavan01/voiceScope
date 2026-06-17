import google.generativeai as genai
from llm_providers.base import LLMProvider, CompletionResult
from typing import Optional
import os


GEMINI_PRICING = {
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


class GeminiProvider(LLMProvider):
    name = "gemini"
    default_model = "gemini-1.5-pro"

    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_name = self.default_model

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[dict] = None,
    ) -> CompletionResult:
        model = model or self.default_model
        model_instance = genai.GenerativeModel(model)

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
        )

        response = await model_instance.generate_content_async(
            prompt,
            generation_config=generation_config,
        )

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0

        return CompletionResult(
            content=response.text,
            model=model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = GEMINI_PRICING.get(model, GEMINI_PRICING["gemini-1.5-pro"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
