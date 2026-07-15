import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from stt_providers.registry import STTRegistry
from stt_providers.base import TranscriptionResult


class TestSTTRegistry:
    def test_list_providers(self):
        providers = STTRegistry.list_providers()
        assert isinstance(providers, list)

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown STT provider"):
            STTRegistry.get("nonexistent_provider_that_does_not_exist")


class TestDeepgramProvider:
    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        from stt_providers.deepgram_provider import DeepgramProvider

        mock_response_data = {
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Hello world",
                        "paragraphs": {
                            "paragraphs": [
                                {"speaker": 0, "sentences": [{"text": "Hello world"}]}
                            ]
                        }
                    }],
                    "detected_language": "en",
                }],
            },
            "metadata": {"duration": 5.0},
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("stt_providers.deepgram_provider.aiohttp.ClientSession", return_value=mock_session):
            provider = DeepgramProvider()
            result = await provider.transcribe(b"fake audio", "test.mp3")

        assert result.transcript == "Hello world"
        assert result.language == "en"
        assert result.duration_seconds == 5.0
        assert len(result.speakers) >= 1

    @pytest.mark.asyncio
    async def test_transcribe_api_error(self):
        from stt_providers.deepgram_provider import DeepgramProvider

        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value="Unauthorized")

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("stt_providers.deepgram_provider.aiohttp.ClientSession", return_value=mock_session):
            provider = DeepgramProvider()
            with pytest.raises(Exception, match="Deepgram API error 401"):
                await provider.transcribe(b"fake audio", "test.mp3")


class TestWhisperProvider:
    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        from stt_providers.whisper_provider import WhisperProvider

        mock_response = MagicMock()
        mock_response.text = "Hello from whisper"
        mock_response.language = "en"
        mock_response.duration = 3.0

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

        with patch("stt_providers.whisper_provider.AsyncOpenAI", return_value=mock_client):
            provider = WhisperProvider()
            result = await provider.transcribe(b"fake audio", "test.mp3")

        assert result.transcript == "Hello from whisper"
        assert result.language == "en"
        assert result.duration_seconds == 3.0

    @pytest.mark.asyncio
    async def test_transcribe_api_error(self):
        from stt_providers.whisper_provider import WhisperProvider

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(side_effect=Exception("Rate limited"))

        with patch("stt_providers.whisper_provider.AsyncOpenAI", return_value=mock_client):
            provider = WhisperProvider()
            with pytest.raises(Exception, match="Rate limited"):
                await provider.transcribe(b"fake audio", "test.mp3")


class TestGeminiSTTProvider:
    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        from stt_providers.gemini_provider import GeminiSTTProvider

        mock_response = MagicMock()
        mock_response.text = "Hello from gemini"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("stt_providers.gemini_provider.genai.Client", return_value=mock_client):
            provider = GeminiSTTProvider()
            result = await provider.transcribe(b"fake audio", "test.mp3")

        assert result.transcript == "Hello from gemini"
        assert len(result.speakers) == 1

    @pytest.mark.asyncio
    async def test_transcribe_rate_limit_retries(self):
        from stt_providers.gemini_provider import GeminiSTTProvider
        import asyncio

        mock_response = MagicMock()
        mock_response.text = "Success after retry"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[Exception("429 rate limited"), mock_response]
        )

        with patch("stt_providers.gemini_provider.genai.Client", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            provider = GeminiSTTProvider()
            result = await provider.transcribe(b"fake audio", "test.mp3")

        assert result.transcript == "Success after retry"

    @pytest.mark.asyncio
    async def test_transcribe_non_retryable_error(self):
        from stt_providers.gemini_provider import GeminiSTTProvider

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        with patch("stt_providers.gemini_provider.genai.Client", return_value=mock_client):
            provider = GeminiSTTProvider()
            with pytest.raises(Exception, match="Invalid API key"):
                await provider.transcribe(b"fake audio", "test.mp3")
