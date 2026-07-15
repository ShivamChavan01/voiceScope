import os
from google import genai
from google.genai import types
from stt_providers.base import STTProvider, TranscriptionResult
from utils.logger import logger


class GeminiSTTProvider(STTProvider):
    name = "gemini"

    MIME_MAP = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }

    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        import asyncio

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        suffix = os.path.splitext(filename)[-1].lstrip(".") or "mp3"
        mime_type = self.MIME_MAP.get(suffix, "audio/mpeg")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        "Transcribe this audio recording exactly. Output ONLY the transcript text, nothing else. Include speaker labels if discernible (e.g. 'Speaker 1:', 'Agent:'). Preserve the natural flow of conversation.",
                    ],
                    config=types.GenerateContentConfig(temperature=0.0),
                )

                transcript = (response.text or "").strip()
                speakers = [{"speaker": 0, "text": transcript}]
                logger.info(f"[STT:gemini] done — {len(transcript)} chars")
                return TranscriptionResult(transcript=transcript, speakers=speakers)

            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"[STT:gemini] rate limited, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                raise
        raise RuntimeError("Gemini transcription failed after all retries")
