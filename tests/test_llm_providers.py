import os
import sys
from unittest.mock import MagicMock

os.environ["DATABASE_URL"] = ""

# Mock mistralai before any import — the package is installed but exports nothing
_mistralai_mock = MagicMock()
_mistralai_mock.MistralAsyncClient = MagicMock()
sys.modules["mistralai"] = _mistralai_mock

import pytest  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402
from types import SimpleNamespace  # noqa: E402


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    def _make_response(self, content="Hello", prompt_tokens=10, completion_tokens=20):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )

    @pytest.mark.asyncio
    async def test_complete_success(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = OpenAIProvider()
            result = await provider.complete("Say hello")

            assert result.content == "Hello"
            assert result.model == "gpt-4o"
            assert result.provider == "openai"
            assert result.input_tokens == 10
            assert result.output_tokens == 20
            assert result.cost_usd > 0

    @pytest.mark.asyncio
    async def test_complete_default_model(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = OpenAIProvider()
            await provider.complete("test")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_custom_model(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = OpenAIProvider()
            await provider.complete("test", model="gpt-4o-mini")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_complete_no_choices_raises(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(choices=[], usage=None)
            )

            provider = OpenAIProvider()
            with pytest.raises(ValueError, match="no choices"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_complete_usage_is_none(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                    usage=None,
                )
            )

            provider = OpenAIProvider()
            result = await provider.complete("test")

            assert result.input_tokens == 0
            assert result.output_tokens == 0

    @pytest.mark.asyncio
    async def test_complete_content_is_none(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
                    usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
                )
            )

            provider = OpenAIProvider()
            result = await provider.complete("test")

            assert result.content == ""

    @pytest.mark.asyncio
    async def test_complete_passes_response_format(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = OpenAIProvider()
            fmt = {"type": "json_object"}
            await provider.complete("test", response_format=fmt)

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["response_format"] == fmt

    def test_estimate_cost_known_model(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI"):
            provider = OpenAIProvider()
            cost = provider.estimate_cost(1000, 500, "gpt-4o")
            assert cost > 0

    def test_estimate_cost_unknown_model(self):
        from llm_providers.openai_provider import OpenAIProvider

        with patch("llm_providers.openai_provider.AsyncOpenAI"):
            provider = OpenAIProvider()
            cost = provider.estimate_cost(1000, 500, "unknown-model")
            assert cost > 0


# ---------------------------------------------------------------------------
# Groq Provider
# ---------------------------------------------------------------------------

class TestGroqProvider:
    def _make_response(self, content="Hi", prompt_tokens=10, completion_tokens=20):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )

    @pytest.mark.asyncio
    async def test_complete_success(self):
        from llm_providers.groq_provider import GroqProvider

        with patch("llm_providers.groq_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = GroqProvider()
            result = await provider.complete("Say hi")

            assert result.content == "Hi"
            assert result.model == "llama-3.3-70b-versatile"
            assert result.provider == "groq"
            assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_complete_default_model(self):
        from llm_providers.groq_provider import GroqProvider

        with patch("llm_providers.groq_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=self._make_response())

            provider = GroqProvider()
            await provider.complete("test")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "llama-3.3-70b-versatile"

    @pytest.mark.asyncio
    async def test_complete_no_choices_raises(self):
        from llm_providers.groq_provider import GroqProvider

        with patch("llm_providers.groq_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(choices=[], usage=None)
            )

            provider = GroqProvider()
            with pytest.raises(ValueError, match="no choices"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_complete_usage_is_none(self):
        from llm_providers.groq_provider import GroqProvider

        with patch("llm_providers.groq_provider.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                    usage=None,
                )
            )

            provider = GroqProvider()
            result = await provider.complete("test")

            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_estimate_cost_always_zero(self):
        from llm_providers.groq_provider import GroqProvider

        with patch("llm_providers.groq_provider.AsyncOpenAI"):
            provider = GroqProvider()
            assert provider.estimate_cost(1000, 500, "llama-3.3-70b-versatile") == 0.0
            assert provider.estimate_cost(100000, 50000, "llama-3.3-70b-versatile") == 0.0


# ---------------------------------------------------------------------------
# Mistral Provider
# ---------------------------------------------------------------------------

class TestMistralProvider:
    def _make_response(self, content="Bonjour", prompt_tokens=10, completion_tokens=20):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )

    @pytest.mark.asyncio
    async def test_complete_success(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(return_value=self._make_response())

            provider = MistralProvider()
            result = await provider.complete("Say bonjour")

            assert result.content == "Bonjour"
            assert result.model == "mistral-large-latest"
            assert result.provider == "mistral"
            assert result.cost_usd > 0

    @pytest.mark.asyncio
    async def test_complete_default_model(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(return_value=self._make_response())

            provider = MistralProvider()
            await provider.complete("test")

            call_kwargs = mock_client.chat.complete_async.call_args[1]
            assert call_kwargs["model"] == "mistral-large-latest"

    @pytest.mark.asyncio
    async def test_complete_no_choices_raises(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(
                return_value=SimpleNamespace(choices=[], usage=None)
            )

            provider = MistralProvider()
            with pytest.raises(ValueError, match="no choices"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_complete_usage_is_none(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                    usage=None,
                )
            )

            provider = MistralProvider()
            result = await provider.complete("test")

            assert result.input_tokens == 0
            assert result.output_tokens == 0

    @pytest.mark.asyncio
    async def test_complete_content_is_none(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
                    usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
                )
            )

            provider = MistralProvider()
            result = await provider.complete("test")

            assert result.content == ""

    def test_estimate_cost_known_model(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient"):
            provider = MistralProvider()
            cost = provider.estimate_cost(1000, 500, "mistral-large-latest")
            assert cost > 0

    def test_estimate_cost_unknown_model(self):
        from llm_providers.mistral_provider import MistralProvider

        with patch("llm_providers.mistral_provider.MistralAsyncClient"):
            provider = MistralProvider()
            cost = provider.estimate_cost(1000, 500, "unknown-model")
            assert cost > 0


# ---------------------------------------------------------------------------
# Ollama Provider
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    def _make_response(self, content="Ollama says hi", prompt_eval_count=100, eval_count=50):
        return SimpleNamespace(
            json=MagicMock(return_value={
                "message": {"content": content},
                "prompt_eval_count": prompt_eval_count,
                "eval_count": eval_count,
            }),
            raise_for_status=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_complete_success(self):
        from llm_providers.ollama_provider import OllamaProvider

        with patch("llm_providers.ollama_provider.httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.post = AsyncMock(return_value=self._make_response())

            provider = OllamaProvider()
            result = await provider.complete("Say hi")

            assert result.content == "Ollama says hi"
            assert result.model == "llama3.1"
            assert result.provider == "ollama"
            assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_complete_default_model(self):
        from llm_providers.ollama_provider import OllamaProvider

        with patch("llm_providers.ollama_provider.httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.post = AsyncMock(return_value=self._make_response())

            provider = OllamaProvider()
            await provider.complete("test")

            call_kwargs = mock_client.post.call_args[1]
            body = call_kwargs["json"]
            assert body["model"] == "llama3.1"

    @pytest.mark.asyncio
    async def test_complete_raises_on_http_error(self):
        import httpx
        from llm_providers.ollama_provider import OllamaProvider

        with patch("llm_providers.ollama_provider.httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock(status_code=500)
            )
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = OllamaProvider()
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_complete_missing_message_keys(self):
        from llm_providers.ollama_provider import OllamaProvider

        with patch("llm_providers.ollama_provider.httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            resp = SimpleNamespace(
                json=MagicMock(return_value={"message": {}}),
                raise_for_status=MagicMock(),
            )
            mock_client.post = AsyncMock(return_value=resp)

            provider = OllamaProvider()
            result = await provider.complete("test")

            assert result.content == ""

    def test_estimate_cost_always_zero(self):
        from llm_providers.ollama_provider import OllamaProvider

        with patch("llm_providers.ollama_provider.httpx.AsyncClient"):
            provider = OllamaProvider()
            assert provider.estimate_cost(1000, 500, "llama3.1") == 0.0


# ---------------------------------------------------------------------------
# Gemini LLM Provider
# ---------------------------------------------------------------------------

class TestGeminiProvider:
    def _make_response(self, content="Gemini says hello", prompt_tokens=10, completion_tokens=20):
        return SimpleNamespace(
            text=content,
            usage_metadata=SimpleNamespace(
                prompt_token_count=prompt_tokens,
                candidates_token_count=completion_tokens,
            ),
        )

    @pytest.mark.asyncio
    async def test_complete_success(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=self._make_response()
            )

            provider = GeminiProvider()
            result = await provider.complete("Say hello")

            assert result.content == "Gemini says hello"
            assert result.model == "gemini-2.0-flash"
            assert result.provider == "gemini"
            assert result.input_tokens == 10
            assert result.output_tokens == 20
            assert result.cost_usd > 0

    @pytest.mark.asyncio
    async def test_complete_default_model(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=self._make_response()
            )

            provider = GeminiProvider()
            await provider.complete("test")

            call_kwargs = mock_client.aio.models.generate_content.call_args[1]
            assert call_kwargs["model"] == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_complete_usage_metadata_none(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=SimpleNamespace(
                    text="ok",
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=None,
                        candidates_token_count=None,
                    ),
                )
            )

            provider = GeminiProvider()
            result = await provider.complete("test")

            assert result.input_tokens == 0
            assert result.output_tokens == 0

    @pytest.mark.asyncio
    async def test_complete_text_is_none(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=SimpleNamespace(
                    text=None,
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=5,
                        candidates_token_count=5,
                    ),
                )
            )

            provider = GeminiProvider()
            result = await provider.complete("test")

            assert result.content == ""

    def test_estimate_cost_known_model(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client"):
            provider = GeminiProvider()
            cost = provider.estimate_cost(1000, 500, "gemini-2.0-flash")
            assert cost > 0

    def test_estimate_cost_unknown_model(self):
        from llm_providers.gemini_provider import GeminiProvider

        with patch("llm_providers.gemini_provider.genai.Client"):
            provider = GeminiProvider()
            cost = provider.estimate_cost(1000, 500, "unknown-model")
            assert cost > 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_list_providers_returns_list(self):
        from llm_providers.registry import ProviderRegistry

        providers = ProviderRegistry.list_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 5

    def test_get_unknown_raises(self):
        from llm_providers.registry import ProviderRegistry

        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderRegistry.get("nonexistent_xyz")

    def test_get_returns_same_instance(self):
        from llm_providers.registry import ProviderRegistry

        with patch("llm_providers.groq_provider.AsyncOpenAI"):
            a = ProviderRegistry.get("groq")
            b = ProviderRegistry.get("groq")
            assert a is b
