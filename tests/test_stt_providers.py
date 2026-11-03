from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stt_providers.registry import STTRegistry


class TestSTTRegistry:
    def test_list_providers(self):
        providers = STTRegistry.list_providers()
        assert isinstance(providers, list)

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown STT provider"):
            STTRegistry.get("nonexistent_provider_that_does_not_exist")


class TestDeepgramProvider:
    async def test_multilingual_configuration_preserves_provider_word_metadata(self, monkeypatch):
        from stt_providers.deepgram_provider import DeepgramProvider
        monkeypatch.setenv('DEEPGRAM_MODEL', 'nova-3')
        monkeypatch.setenv('DEEPGRAM_LANGUAGE', 'multi')
        words = [{'word': 'hello', 'start': 0.1, 'end': 0.5, 'speaker': 1, 'language': 'en'}]
        response = AsyncMock(status=200)
        response.json.return_value = {'results': {'channels': [{'alternatives': [{'transcript': 'hello', 'words': words}]}]}}
        session = MagicMock()
        session.__aenter__.return_value = session
        session.post.return_value.__aenter__ = AsyncMock(return_value=response)
        session.post.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch('stt_providers.deepgram_provider.aiohttp.ClientSession', return_value=session):
            result = await DeepgramProvider().transcribe(b'audio', 'call.wav')
        options = session.post.call_args.kwargs
        assert options['params']['model'] == 'nova-3'
        assert options['params']['language'] == 'multi'
        assert options['headers']['Content-Type'] == 'audio/wav'
        assert result.words == words

    @pytest.mark.parametrize('model,language', [('unknown', 'en'), ('nova-3', 'unknown'), ('nova-2', 'multi')])
    async def test_invalid_configuration_fails_before_network(self, monkeypatch, model, language):
        from stt_providers.deepgram_provider import DeepgramProvider
        monkeypatch.setenv('DEEPGRAM_MODEL', model)
        monkeypatch.setenv('DEEPGRAM_LANGUAGE', language)
        with patch('stt_providers.deepgram_provider.aiohttp.ClientSession') as session:
            with pytest.raises(ValueError):
                await DeepgramProvider().transcribe(b'audio', 'call.wav')
        session.assert_not_called()

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


@pytest.mark.asyncio
async def test_deepgram_preserves_word_timestamps_and_speaker_metadata():
    from stt_providers.deepgram_provider import DeepgramProvider
    word = {'word': 'hello', 'start': 1.2, 'end': 1.8, 'speaker': 2, 'confidence': 0.91}
    response = AsyncMock(status=200)
    response.json.return_value = {'results': {'channels': [{'alternatives': [{'transcript': 'hello', 'words': [word]}]}]}}
    context = AsyncMock()
    context.__aenter__.return_value = response
    session = MagicMock()
    session.post.return_value = context
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with patch('stt_providers.deepgram_provider.aiohttp.ClientSession', return_value=session):
        result = await DeepgramProvider().transcribe(b'audio', 'call.wav')
    assert result.words == [word]
    assert result.speakers[0]['speaker'] == 2
