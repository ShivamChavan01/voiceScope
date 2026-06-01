from openai import AsyncOpenAI
from core.context import PipelineContext
from utils.logger import logger
import tempfile
import os


class TranscriptionAgent:
    """
    Agent 1 — Converts uploaded audio to clean text using OpenAI Whisper.
    Populates: ctx.raw_transcript, ctx.audio_duration_seconds, ctx.language_detected
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def run(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        logger.info(f"[TranscriptionAgent] run_id={ctx.run_id} file={filename}")

        # Write audio bytes to a temp file — Whisper API needs a file object
        suffix = os.path.splitext(filename)[-1] or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"  # gives us language + duration too
                )

            ctx.raw_transcript = response.text
            ctx.language_detected = getattr(response, "language", "unknown")
            ctx.audio_duration_seconds = getattr(response, "duration", None)
            ctx.mark_stage("transcription")

            logger.info(f"[TranscriptionAgent] done — {len(ctx.raw_transcript)} chars, lang={ctx.language_detected}")

        except Exception as e:
            ctx.add_error("transcription", str(e))
            logger.error(f"[TranscriptionAgent] failed — {e}")

        finally:
            os.unlink(tmp_path)

        return ctx
