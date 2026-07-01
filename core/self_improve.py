"""
Self-Improvement Loop — orchestrates benchmark → optimize → track → improve.
This is the "loop engineering" that makes VoiceScope grow stronger over time.
"""

import time
from pydantic import BaseModel, Field
from core.benchmark import HarnessBenchmark, BenchmarkSummary
from core.optimizer import CalibrationOptimizer, OptimizationResult
from core.prompt_tracker import PromptTracker
from utils.logger import logger


class LoopResult(BaseModel):
    timestamp: float = 0.0
    benchmark: BenchmarkSummary = Field(default_factory=BenchmarkSummary)
    optimization: OptimizationResult = Field(default_factory=OptimizationResult)
    suggestions: list[dict] = Field(default_factory=list)
    prompt_stats: list[dict] = Field(default_factory=list)
    status: str = "completed"


class SelfImprovementLoop:
    """Orchestrates the full self-improvement cycle."""

    def __init__(self):
        self.benchmark = HarnessBenchmark()
        self.optimizer = CalibrationOptimizer()
        self.prompt_tracker = PromptTracker()

    def run(self) -> LoopResult:
        """Run one full improvement cycle."""
        logger.info("[SelfImprovement] starting improvement loop")

        # Step 1: Run benchmark on labeled test data
        bench_summary = self.benchmark.run_benchmark()
        logger.info(
            f"[SelfImprovement] benchmark — {bench_summary.total_tests} tests, "
            f"avg_truth_score={bench_summary.avg_truth_score}, "
            f"weakest={bench_summary.weakest_layer}"
        )

        # Step 2: Optimize weights based on benchmark
        bench_dicts = [r.model_dump() for r in bench_summary.results]
        opt_result = self.optimizer.optimize(bench_dicts)
        logger.info(
            f"[SelfImprovement] optimization — improvement={opt_result.improvement}, "
            f"changes={len(opt_result.changes_made)}"
        )

        # Step 3: Track prompt performance
        self.prompt_tracker.record_run(
            "analysis_prompt",
            bench_summary.sentiment_accuracy,
            [e for r in bench_summary.results for e in r.errors],
        )

        # Step 4: Get improvement suggestions
        suggestions = self.prompt_tracker.get_suggestions()
        prompt_stats = self.prompt_tracker.get_prompt_stats()

        # Record to calibration
        from core.calibration import ConfidenceCalibrator
        cal = ConfidenceCalibrator()
        cal.record(
            run_id=f"benchmark-{int(time.time())}",
            truth_score=bench_summary.avg_truth_score,
            confidence="high" if bench_summary.avg_truth_score >= 0.85 else
                       "medium" if bench_summary.avg_truth_score >= 0.70 else "low",
        )

        result = LoopResult(
            timestamp=time.time(),
            benchmark=bench_summary,
            optimization=opt_result,
            suggestions=suggestions,
            prompt_stats=prompt_stats,
        )

        logger.info(
            f"[SelfImprovement] loop complete — truth_score={bench_summary.avg_truth_score}, "
            f"optimization_improvement={opt_result.improvement}"
        )

        return result

    def get_status(self) -> dict:
        """Get current state of the self-improvement system."""
        return {
            "optimizer_weights": self.optimizer.get_current_weights(),
            "optimization_history": len(self.optimizer.get_history()),
            "prompt_stats": self.prompt_tracker.get_prompt_stats(),
            "suggestions": self.prompt_tracker.get_suggestions()[:5],
        }
