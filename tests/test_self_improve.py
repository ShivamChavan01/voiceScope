import os

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["CALIBRATION_DB_PATH"] = ":memory:"
os.environ["OPTIMIZER_DB_PATH"] = ":memory:"
os.environ["PROMPT_TRACKER_DB_PATH"] = ":memory:"

from core.benchmark import HarnessBenchmark
from core.optimizer import CalibrationOptimizer, OptimizationResult
from core.prompt_tracker import PromptTracker
from core.self_improve import SelfImprovementLoop, LoopResult


# ─── Benchmark Tests ─────────────────────────────────────────────────


class TestBenchmark:
    def test_load_test_data(self):
        bench = HarnessBenchmark()
        data = bench.load_test_data()
        assert len(data) == 10
        assert data[0]["id"] == "TD-001"

    def test_run_single(self):
        bench = HarnessBenchmark()
        data = bench.load_test_data()
        result = bench._run_single(data[0])
        assert result.test_id == "TD-001"
        assert result.truth_score > 0
        assert result.sentiment_correct
        assert result.outcome_correct

    def test_run_benchmark(self):
        bench = HarnessBenchmark()
        summary = bench.run_benchmark()
        assert summary.total_tests == 10
        assert summary.avg_truth_score > 0.5
        assert summary.sentiment_accuracy >= 0.7
        assert summary.outcome_accuracy >= 0.5
        assert summary.weakest_layer != ""
        assert summary.strongest_layer != ""

    def test_benchmark_sentiments_reasonable(self):
        bench = HarnessBenchmark()
        summary = bench.run_benchmark()
        # Harness catches mismatches — accuracy should be decent
        assert summary.sentiment_accuracy >= 0.7

    def test_benchmark_outcomes_reasonable(self):
        bench = HarnessBenchmark()
        summary = bench.run_benchmark()
        # Outcome evidence check is stricter — some cases lack explicit markers
        assert summary.outcome_accuracy >= 0.5

    def test_benchmark_covers_all_layers(self):
        bench = HarnessBenchmark()
        summary = bench.run_benchmark()
        for r in summary.results:
            assert "schema" in r.layer_scores


# ─── Optimizer Tests ─────────────────────────────────────────────────


class TestOptimizer:
    def test_default_weights(self):
        opt = CalibrationOptimizer(":memory:")
        weights = opt.get_current_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert "schema" in weights
        assert "citations" in weights

    def test_optimize(self):
        opt = CalibrationOptimizer(":memory:")
        # Simulate benchmark results
        results = [
            {"layer_scores": {"schema": 1.0, "citations": 0.8, "facts": 0.9}},
            {"layer_scores": {"schema": 1.0, "citations": 0.6, "facts": 0.7}},
        ]
        result = opt.optimize(results)
        assert isinstance(result, OptimizationResult)
        assert len(result.new_weights) > 0
        assert abs(sum(result.new_weights.values()) - 1.0) < 0.01

    def test_optimize_preserves_critical_layers(self):
        opt = CalibrationOptimizer(":memory:")
        results = [{"layer_scores": {"schema": 0.1, "citations": 0.1, "other": 1.0}}]
        result = opt.optimize(results)
        # Schema and citations should have minimum weight
        assert result.new_weights.get("schema", 0) >= 0.05
        assert result.new_weights.get("citations", 0) >= 0.05

    def test_optimize_tracks_history(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        opt = CalibrationOptimizer(path)
        results = [{"layer_scores": {"schema": 1.0}}]
        opt.optimize(results)
        opt.optimize(results)
        assert len(opt.get_history()) == 2
        os.unlink(path)


# ─── Prompt Tracker Tests ────────────────────────────────────────────


class TestPromptTracker:
    def test_record_run(self):
        tracker = PromptTracker(":memory:")
        tracker.record_run("analysis_prompt", 0.85, ["sentiment mismatch"])
        stats = tracker.get_prompt_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "analysis_prompt"
        assert stats[0]["accuracy"] == 0.85
        assert stats[0]["total_runs"] == 1

    def test_record_multiple_runs(self):
        tracker = PromptTracker(":memory:")
        tracker.record_run("analysis_prompt", 0.8)
        tracker.record_run("analysis_prompt", 0.9)
        stats = tracker.get_prompt_stats()
        assert stats[0]["total_runs"] == 2
        # Running average: (0.8 + 0.9) / 2 = 0.85
        assert abs(stats[0]["accuracy"] - 0.85) < 0.01

    def test_get_suggestions(self):
        tracker = PromptTracker(":memory:")
        tracker.record_run("p1", 0.5, ["sentiment mismatch", "outcome mismatch"])
        tracker.record_run("p2", 0.6, ["sentiment mismatch"])
        suggestions = tracker.get_suggestions()
        assert len(suggestions) > 0
        # sentiment_mismatch should be most common
        assert suggestions[0]["pattern"] == "sentiment_mismatch"

    def test_failure_categorization(self):
        tracker = PromptTracker(":memory:")
        assert tracker._categorize_error("sentiment mismatch") == "sentiment_mismatch"
        assert tracker._categorize_error("outcome not resolved") == "outcome_mismatch"
        assert tracker._categorize_error("escalation signal wrong") == "escalation_mismatch"
        assert tracker._categorize_error("citation unmatched finding") == "citation_failure"
        assert tracker._categorize_error("fact contradiction detected") == "fact_contradiction"

    def test_suggest_fix(self):
        tracker = PromptTracker(":memory:")
        fix = tracker._suggest_fix("sentiment_mismatch")
        assert "sentiment" in fix.lower()
        fix = tracker._suggest_fix("citation_failure")
        assert "citation" in fix.lower() or "grounded" in fix.lower()


# ─── Self-Improvement Loop Tests ─────────────────────────────────────


class TestSelfImprovementLoop:
    def test_run_loop(self):
        loop = SelfImprovementLoop()
        result = loop.run()
        assert isinstance(result, LoopResult)
        assert result.status == "completed"
        assert result.benchmark.total_tests == 10
        assert result.benchmark.avg_truth_score > 0
        assert len(result.suggestions) >= 0

    def test_loop_status(self):
        loop = SelfImprovementLoop()
        status = loop.get_status()
        assert "optimizer_weights" in status
        assert "prompt_stats" in status
        assert "suggestions" in status

    def test_loop_benchmark_summary(self):
        loop = SelfImprovementLoop()
        result = loop.run()
        assert result.benchmark.sentiment_accuracy >= 0.7
        assert result.benchmark.outcome_accuracy >= 0.5
        assert result.benchmark.escalation_accuracy >= 0.7
