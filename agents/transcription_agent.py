from core.context import PipelineContext
from utils.logger import logger
from stt_providers.registry import STTRegistry


class TranscriptionAgent:
    """
    Agent 1 — Converts uploaded audio to clean text.
    Supports Deepgram, OpenAI Whisper, and Gemini (native audio understanding).
    Populates: ctx.raw_transcript, ctx.audio_duration_seconds, ctx.language_detected
    """

    def __init__(self):
        self._provider_name = None

    async def run(self, ctx: PipelineContext, audio_bytes: bytes, filename: str) -> PipelineContext:
        provider = STTRegistry.get(self._provider_name)
        logger.info(f"[TranscriptionAgent] run_id={ctx.run_id} file={filename} provider={provider.name}")

        try:
            result = await provider.transcribe(audio_bytes, filename)
            ctx.raw_transcript = result.transcript
            ctx.transcript_speakers = result.speakers
            ctx.language_detected = result.language
            ctx.audio_duration_seconds = result.duration_seconds
            ctx.mark_stage("transcription")
        except Exception as e:
            ctx.add_error("transcription", str(e))
            logger.error(f"[TranscriptionAgent] {provider.name} failed — {e}")

        return ctx
