from agents.transcription_agent import TranscriptionAgent
from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportAgent
from core.context import PipelineContext
from core.knowledge_base import KnowledgeBase
from core.harness import ValidationHarness
from core.audio_quality import AudioQualityChecker
from storage.chroma_store import ChromaStore
from utils.logger import logger


class VoiceScopePipeline:
    """
    Orchestrates the 3-agent pipeline:
    TranscriptionAgent → AnalysisAgent → ReportAgent

    Each agent receives the shared PipelineContext and enriches it.
    Validation harness wraps every stage.
    """

    def __init__(self):
        self.chroma = ChromaStore()
        self.kb = KnowledgeBase()
        self.transcription_agent = TranscriptionAgent()
        self.analysis_agent = AnalysisAgent(self.chroma, self.kb)
        self.report_agent = ReportAgent(self.chroma)
        self.harness = ValidationHarness()
        self.audio_checker = AudioQualityChecker()

    async def run(self, audio_bytes: bytes, filename: str) -> dict:
        ctx = PipelineContext()
        logger.info(f"[Pipeline] starting run_id={ctx.run_id}")

        # Layer 11: Audio Quality Pre-Check
        audio_quality = self.audio_checker.check(audio_bytes, filename)
        ctx.report = {"audio_quality": audio_quality.model_dump()}
        if not audio_quality.should_proceed:
            logger.warning(f"[Pipeline] audio quality too low: {audio_quality.issues}")
            ctx.add_error("audio_quality", str(audio_quality.issues))
            return {"run_id": ctx.run_id, "audio_quality": audio_quality.model_dump(), "status": "failed"}

        # Stage 1 — Transcription
        ctx = await self.transcription_agent.run(ctx, audio_bytes, filename)

        # Stage 2 — Analysis (only if transcription succeeded)
        if "transcription" in ctx.stages_completed:
            ctx = await self.analysis_agent.run(ctx)
        else:
            logger.warning("[Pipeline] skipping analysis — transcription failed")

        # Stage 3 — Report (always runs, handles partial data gracefully)
        ctx = await self.report_agent.run(ctx)

        # Run Validation Harness (Layers 1-10, 12)
        harness_result = self.harness.validate_pipeline(ctx)
        logger.info(
            f"[Pipeline] harness — truth_score={harness_result.truth_score}, "
            f"confidence={harness_result.confidence}, "
            f"errors={len(harness_result.validation_errors)}"
        )

        logger.info(f"[Pipeline] completed run_id={ctx.run_id} stages={ctx.stages_completed}")
        report = ctx.report or {"run_id": ctx.run_id, "errors": ctx.errors, "status": "failed"}
        report["harness"] = harness_result.model_dump()
        return report
