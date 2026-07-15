import os
import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

from unittest.mock import patch


class TestCLIHelp:
    def test_help_exits_cleanly(self):
        from cli import main
        with patch("sys.argv", ["voicescope", "--help"]):
            main()

    def test_no_args_shows_usage(self):
        from cli import main
        with patch("sys.argv", ["voicescope"]):
            main()

    def test_unknown_command(self):
        from cli import main
        with patch("sys.argv", ["voicescope", "bogus"]):
            with pytest.raises(SystemExit):
                main()


class TestCLIStatus:
    def test_status_runs(self):
        from cli import _cmd_status
        _cmd_status()


class TestCLIFormatReport:
    def test_format_report_basic(self):
        from cli import _format_report
        result = {
            "harness": {"truth_score": 0.85, "confidence": "high", "layer_scores": {"schema": 0.9}},
            "raw_transcript": "Agent: Hello\nCustomer: Hi",
            "intent": "greeting",
            "sentiment_arc": "positive",
            "outcome": "resolved",
            "hallucination_detected": False,
            "errors": [],
        }
        output = _format_report(result)
        assert "0.85" in output
        assert "greeting" in output
        assert "PASS" in output

    def test_format_report_with_hallucination(self):
        from cli import _format_report
        result = {
            "harness": {"truth_score": 0.3, "confidence": "low", "layer_scores": {}},
            "raw_transcript": "test",
            "hallucination_detected": True,
            "hallucination_evidence": "Agent promised free shipping",
            "errors": ["schema validation failed"],
        }
        output = _format_report(result)
        assert "FAIL" in output
        assert "Hallucination Detected" in output

    def test_format_report_with_cost(self):
        from cli import _format_report
        result = {
            "harness": {"truth_score": 0.9, "confidence": "high", "layer_scores": {}},
            "provider": {"cost_usd": 0.0042, "model": "gpt-4o"},
        }
        output = _format_report(result)
        assert "$0.0042" in output


class TestCLIAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_missing_file(self):
        from cli import _cmd_analyze
        with pytest.raises(SystemExit):
            await _cmd_analyze("nonexistent.mp3")

    @pytest.mark.asyncio
    async def test_analyze_file_too_large(self, tmp_path):
        from cli import _cmd_analyze
        big_file = tmp_path / "big.mp3"
        big_file.write_bytes(b"x" * (26 * 1024 * 1024))
        with pytest.raises(SystemExit):
            await _cmd_analyze(str(big_file))
