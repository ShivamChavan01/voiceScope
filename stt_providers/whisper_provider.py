import os
import tempfile
from openai import AsyncOpenAI
from stt_providers.base import STTProvider, TranscriptionResult
from utils.logger import logger


class WhisperProvider(STTProvider):
    name = "whisper"

    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        suffix = os.path.splitext(filename)[-1] or ".mp3"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                response = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                )

            transcript = response.text
            language = getattr(response, "language", "unknown")
            duration = getattr(response, "duration", None)
            speakers = [{"speaker": 0, "text": transcript}]

            logger.info(f"[STT:whisper] done — {len(transcript)} chars, lang={language}")
            return TranscriptionResult(transcript=transcript, speakers=speakers, language=language, duration_seconds=duration)

        finally:
            os.unlink(tmp_path)
