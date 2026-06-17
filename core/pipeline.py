from agents.transcription_agent import TranscriptionAgent
from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportAgent
from core.context import PipelineContext
from storage.chroma_store import ChromaStore
from utils.logger import logger


class VoiceScopePipeline:
    """
    Orchestrates the 3-agent pipeline:
    TranscriptionAgent → AnalysisAgent → ReportAgent

    Each agent receives the shared PipelineContext and enriches it.
    """

    def __init__(self):
        self.chroma = ChromaStore()
        self.transcription_agent = TranscriptionAgent()
        self.analysis_agent = AnalysisAgent(self.chroma)
        self.report_agent = ReportAgent(self.chroma)

    async def run(self, audio_bytes: bytes, filename: str) -> dict:
        ctx = PipelineContext()
        logger.info(f"[Pipeline] starting run_id={ctx.run_id}")

        # Stage 1 — Transcription
        ctx = await self.transcription_agent.run(ctx, audio_bytes, filename)

        # Stage 2 — Analysis (only if transcription succeeded)
        if "transcription" in ctx.stages_completed:
            ctx = await self.analysis_agent.run(ctx)
        else:
            logger.warning("[Pipeline] skipping analysis — transcription failed")

        # Stage 3 — Report (always runs, handles partial data gracefully)
        ctx = await self.report_agent.run(ctx)

        logger.info(f"[Pipeline] completed run_id={ctx.run_id} stages={ctx.stages_completed}")
        return ctx.report or {"run_id": ctx.run_id, "errors": ctx.errors, "status": "failed"}
