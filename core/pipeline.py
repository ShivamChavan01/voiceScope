from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportAgent
from agents.speaker_agent import SpeakerAgent
from agents.transcription_agent import TranscriptionAgent
from core.audio_quality import AudioQualityChecker
from core.context import PipelineContext
from core.harness import ValidationHarness
from core.knowledge_base import KnowledgeBase
from core.speakers import attributed_transcript, parse_speaker_turns
from core.speech_diagnostics import SpeechDiagnostics
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
        self.speaker_agent = SpeakerAgent()
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

        return await self._finish(ctx)

    async def run_from_transcript(self, transcript: str) -> dict:
        """Transcript-only run — skips audio/STT stages (UI testing, debugging)."""
        ctx = PipelineContext()
        logger.info(f"[Pipeline] starting transcript-only run_id={ctx.run_id}")
        ctx.raw_transcript = transcript
        ctx.word_count = len(transcript.split())
        ctx.mark_stage("transcription")
        return await self._finish(ctx)

    async def attribute_speakers(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.transcript_speakers:
            ctx.transcript_speakers = parse_speaker_turns(ctx.raw_transcript or "") or None
            if not ctx.transcript_speakers and (ctx.raw_transcript or "").strip():
                ctx.transcript_speakers = [{
                    "speaker": 0, "text": ctx.raw_transcript,
                    "diarization_source": "unavailable",
                }]
        if ctx.transcript_speakers:
            ctx = await self.speaker_agent.run(ctx)
            ctx.attributed_transcript = attributed_transcript(ctx.transcript_speakers or [])
        return ctx

    async def assess_reliability(self, ctx: PipelineContext) -> PipelineContext:
        from core.policy_store import PolicyStore
        from core.reliability import ReliabilityReport, evaluate_reliability

        try:
            policies = await PolicyStore().list_rules()
            ctx.reliability = evaluate_reliability(ctx.transcript_speakers or [], policies).model_dump(mode="json")
        except Exception:
            logger.exception("[Pipeline] policy assessment unavailable")
            ctx.reliability = ReliabilityReport(
                status="insufficient_evidence",
                limitations=["Policy configuration could not be loaded; no compliance conclusion is available."],
            ).model_dump(mode="json")
            ctx.add_error("policy", "Policy assessment unavailable")
        return ctx

    async def _finish(self, ctx: PipelineContext) -> dict:
        # Stage 2 — Analysis (only if transcription succeeded)
        if "transcription" in ctx.stages_completed:
            ctx = await self.attribute_speakers(ctx)
            ctx = await self.assess_reliability(ctx)
            ctx = await self.analysis_agent.run(ctx)
        else:
            logger.warning("[Pipeline] skipping analysis — transcription failed")

        # Never ask a model to fabricate a report after an upstream failure.
        if "analysis" in ctx.stages_completed:
            ctx = await self.report_agent.run(ctx)
        else:
            ctx.report = {"run_id": ctx.run_id, "status": "failed", "analysis": {}}

        # Run Validation Harness (Layers 1-10, 12)
        harness_result = self.harness.validate_pipeline(ctx)
        logger.info(
            f"[Pipeline] harness — truth_score={harness_result.truth_score}, "
            f"confidence={harness_result.confidence}, "
            f"errors={len(harness_result.validation_errors)}"
        )

        logger.info(f"[Pipeline] completed run_id={ctx.run_id} stages={ctx.stages_completed}")
        return self.finalize_result(ctx, harness_result)

    def finalize_result(self, ctx: PipelineContext, harness_result) -> dict:
        """Use identical failure states for regular and streaming evaluations."""
        report = ctx.report or {"run_id": ctx.run_id, "status": "failed"}
        report["run_id"] = ctx.run_id
        report["score_contract"] = "heuristic_consistency_v2"
        if ctx.reliability is not None:
            report["reliability"] = ctx.reliability
        report.setdefault("speech_diagnostics", SpeechDiagnostics(
            limitations=["No Bolna speech measurements were supplied for this evaluation."]
        ).model_dump())
        report["harness"] = harness_result.model_dump()
        report["errors"] = ctx.errors
        if "analysis" not in ctx.stages_completed or "report" not in ctx.stages_completed:
            report["status"] = "failed"
            report["evaluation_status"] = "failed"
        elif ctx.errors or not harness_result.validation_passed:
            report["status"] = "partial"
            report["evaluation_status"] = "needs_review"
        else:
            report["status"] = "completed"
            report["evaluation_status"] = "validated"
        report["attributed_transcript"] = ctx.attributed_transcript
        report["raw_transcript"] = ctx.raw_transcript
        report["transcript_speakers"] = ctx.transcript_speakers
        return report
