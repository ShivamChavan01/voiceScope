from core.cross_check import CrossChecker


class TestCrossCheck:
    def test_consistent_analysis(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "positive",
            "outcome": "resolved",
            "hallucination_detected": False,
            "escalation_signal": False,
            "findings": [{"topic": "test"}],
            "quality_score": 85,
        })
        assert result.consistent is True
        assert result.score == 1.0
        assert len(result.inconsistencies) == 0

    def test_negative_sentiment_resolved(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "negative",
            "outcome": "resolved",
            "hallucination_detected": False,
            "escalation_signal": False,
        })
        assert result.consistent is False
        assert any("negative" in i and "resolved" in i for i in result.inconsistencies)

    def test_escalation_resolved_contradiction(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "neutral",
            "outcome": "resolved",
            "hallucination_detected": False,
            "escalation_signal": True,
        })
        assert result.consistent is False
        assert any("escalation" in i and "resolved" in i for i in result.inconsistencies)

    def test_hallucination_no_findings(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "neutral",
            "outcome": "resolved",
            "hallucination_detected": True,
            "escalation_signal": False,
            "findings": [],
        })
        assert result.consistent is False
        assert any("hallucination" in i and "findings" in i for i in result.inconsistencies)

    def test_high_quality_with_hallucination(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "neutral",
            "outcome": "resolved",
            "hallucination_detected": True,
            "escalation_signal": False,
            "findings": [{"topic": "test"}],
            "quality_score": 90,
        })
        assert result.consistent is False
        assert any("quality_score" in i and "hallucination" in i for i in result.inconsistencies)

    def test_multiple_inconsistencies_reduce_score(self):
        checker = CrossChecker()
        result = checker.check({
            "sentiment_arc": "negative",
            "outcome": "resolved",
            "hallucination_detected": True,
            "escalation_signal": True,
            "findings": [],
            "quality_score": 90,
        })
        assert result.consistent is False
        assert len(result.inconsistencies) >= 3
        assert result.score < 0.5
