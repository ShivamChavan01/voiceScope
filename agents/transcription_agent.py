from core.context import PipelineContext
from utils.logger import logger
import tempfile
import os


class TranscriptionAgent:
    """
    Agent 1 — Converts uploaded audio to clean text.
    Supports Deepgram, OpenAI Whisper, and Gemini (native audio understanding).
    Populates: ctx.raw_transcript, ctx.audio_duration_seconds, ctx.language_detected
    """

    def __init__(self):
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        explicit = os.getenv("STT_PROVIDER", "").lower()
        if explicit in ("deepgram", "whisper", "gemini"):
            return explicit
        if os.getenv("DEEPGRAM_API_KEY"):
            return "deepgram"
        if os.getenv("LLM_PROVIDER") == "gemini" or (
            os.getenv("GOOGLE_API_KEY") and not os.getenv("OPENAI_API_KEY")
        ):
            return "gemini"
        return "whisper"

    async def run(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        logger.info(f"[TranscriptionAgent] run_id={ctx.run_id} file={filename} provider={self.provider}")

        if self.provider == "deepgram":
            return await self._transcribe_deepgram(ctx, audio_bytes, filename)
        if self.provider == "gemini":
            return await self._transcribe_gemini(ctx, audio_bytes, filename)
        return await self._transcribe_whisper(ctx, audio_bytes, filename)

    async def _transcribe_deepgram(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        import aiohttp

        api_key = os.getenv("DEEPGRAM_API_KEY")
        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": "nova-2",
            "smart_format": "true",
            "diarize": "true",
            "punctuate": "true",
            "language": "en",
        }
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/mpeg",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=audio_bytes, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise Exception(f"Deepgram API error {resp.status}: {body}")

                    data = await resp.json()

            channels = data.get("results", {}).get("channels", [])
            if not channels:
                raise Exception("Deepgram returned no channels")

            transcript = channels[0].get("alternatives", [{}])[0].get("transcript", "")
            ctx.raw_transcript = transcript
            ctx.language_detected = data.get("results", {}).get("channels", [{}])[0].get("detected_language", "unknown")
            ctx.audio_duration_seconds = data.get("metadata", {}).get("duration")
            ctx.mark_stage("transcription")

            logger.info(f"[TranscriptionAgent] deepgram done — {len(transcript)} chars, lang={ctx.language_detected}")

        except Exception as e:
            ctx.add_error("transcription", str(e))
            logger.error(f"[TranscriptionAgent] deepgram failed — {e}")

        return ctx

    async def _transcribe_gemini(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        import asyncio
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        suffix = os.path.splitext(filename)[-1].lstrip(".") or "mp3"
        mime_map = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "webm": "audio/webm",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
        }
        mime_type = mime_map.get(suffix, "audio/mpeg")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        "Transcribe this audio recording exactly. Output ONLY the transcript text, nothing else. Include speaker labels if discernible (e.g. 'Speaker 1:', 'Agent:'). Preserve the natural flow of conversation.",
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                    ),
                )

                transcript = response.text.strip()
                ctx.raw_transcript = transcript
                ctx.language_detected = "unknown"
                ctx.audio_duration_seconds = None
                ctx.mark_stage("transcription")

                logger.info(f"[TranscriptionAgent] gemini done — {len(transcript)} chars")
                break

            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"[TranscriptionAgent] rate limited, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                ctx.add_error("transcription", error_str)
                logger.error(f"[TranscriptionAgent] gemini failed — {e}")

        return ctx

    async def _transcribe_whisper(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        from openai import AsyncOpenAI

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

            ctx.raw_transcript = response.text
            ctx.language_detected = getattr(response, "language", "unknown")
            ctx.audio_duration_seconds = getattr(response, "duration", None)
            ctx.mark_stage("transcription")

            logger.info(
                f"[TranscriptionAgent] whisper done — {len(ctx.raw_transcript)} chars, lang={ctx.language_detected}"
            )

        except Exception as e:
            ctx.add_error("transcription", str(e))
            logger.error(f"[TranscriptionAgent] whisper failed — {e}")

        finally:
            os.unlink(tmp_path)

        return ctx
