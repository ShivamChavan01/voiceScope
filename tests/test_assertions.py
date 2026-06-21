from core.assertions import AssertionEngine, AssertionResult


engine = AssertionEngine()


def _make_report(
    intent="test", outcome="resolved", esc=False, halluc=False, sentiment="neutral", quality=75
):
    return {
        "analysis": {
            "intent": intent,
            "outcome": outcome,
            "escalation_signal": esc,
            "hallucination_detected": halluc,
            "sentiment_arc": sentiment,
        },
        "report": {
            "quality_score": quality,
            "executive_summary": "test summary",
            "key_findings": ["finding1"],
            "recommendations": ["rec1"],
        },
    }


class TestAssertionResult:
    def test_to_dict(self):
        r = AssertionResult("outcome", "resolved", "resolved", True, "")
        d = r.to_dict()
        assert d["field"] == "outcome"
        assert d["passed"] is True
        assert d["expected"] == "resolved"
        assert d["actual"] == "resolved"

    def test_to_dict_with_message(self):
        r = AssertionResult("outcome", "resolved", "escalated", False, "mismatch")
        d = r.to_dict()
        assert d["passed"] is False
        assert d["message"] == "mismatch"


class TestIntentContains:
    def test_match(self):
        report = _make_report(intent="cancel subscription")
        results = engine.evaluate({"intent_contains": "cancel"}, report)
        assert len(results) == 1
        assert results[0].passed is True

    def test_no_match(self):
        report = _make_report(intent="billing question")
        results = engine.evaluate({"intent_contains": "cancel"}, report)
        assert results[0].passed is False
        assert "does not contain" in results[0].message

    def test_case_insensitive(self):
        report = _make_report(intent="Cancel Subscription")
        results = engine.evaluate({"intent_contains": "cancel"}, report)
        assert results[0].passed is True

    def test_missing_intent(self):
        report = {"analysis": {}, "report": {"quality_score": 50}}
        results = engine.evaluate({"intent_contains": "test"}, report)
        assert results[0].passed is False


class TestOutcome:
    def test_match(self):
        report = _make_report(outcome="resolved")
        results = engine.evaluate({"outcome": "resolved"}, report)
        assert results[0].passed is True

    def test_mismatch(self):
        report = _make_report(outcome="escalated")
        results = engine.evaluate({"outcome": "resolved"}, report)
        assert results[0].passed is False
        assert "escalated" in results[0].message


class TestEscalationSignal:
    def test_true_match(self):
        report = _make_report(esc=True)
        results = engine.evaluate({"escalation_signal": True}, report)
        assert results[0].passed is True

    def test_false_match(self):
        report = _make_report(esc=False)
        results = engine.evaluate({"escalation_signal": False}, report)
        assert results[0].passed is True

    def test_mismatch(self):
        report = _make_report(esc=True)
        results = engine.evaluate({"escalation_signal": False}, report)
        assert results[0].passed is False


class TestHallucination:
    def test_true_match(self):
        report = _make_report(halluc=True)
        results = engine.evaluate({"hallucination_detected": True}, report)
        assert results[0].passed is True

    def test_false_match(self):
        report = _make_report(halluc=False)
        results = engine.evaluate({"hallucination_detected": False}, report)
        assert results[0].passed is True


class TestSentimentArc:
    def test_match(self):
        report = _make_report(sentiment="positive")
        results = engine.evaluate({"sentiment_arc": "positive"}, report)
        assert results[0].passed is True

    def test_mismatch(self):
        report = _make_report(sentiment="negative")
        results = engine.evaluate({"sentiment_arc": "positive"}, report)
        assert results[0].passed is False


class TestMinQualityScore:
    def test_above_minimum(self):
        report = _make_report(quality=85)
        results = engine.evaluate({"min_quality_score": 70}, report)
        assert results[0].passed is True

    def test_exact_minimum(self):
        report = _make_report(quality=70)
        results = engine.evaluate({"min_quality_score": 70}, report)
        assert results[0].passed is True

    def test_below_minimum(self):
        report = _make_report(quality=50)
        results = engine.evaluate({"min_quality_score": 70}, report)
        assert results[0].passed is False
        assert "50" in results[0].message
        assert "70" in results[0].message

    def test_missing_quality_score(self):
        report = {"analysis": {}, "report": {}}
        results = engine.evaluate({"min_quality_score": 70}, report)
        assert results[0].passed is False


class TestMultipleAssertions:
    def test_all_pass(self):
        report = _make_report(
            intent="cancel subscription",
            outcome="resolved",
            esc=False,
            halluc=False,
            sentiment="negative",
            quality=80,
        )
        expected = {
            "intent_contains": "cancel",
            "outcome": "resolved",
            "escalation_signal": False,
            "hallucination_detected": False,
            "sentiment_arc": "negative",
            "min_quality_score": 60,
        }
        results = engine.evaluate(expected, report)
        assert len(results) == 6
        assert all(r.passed for r in results)

    def test_one_fails(self):
        report = _make_report(
            intent="cancel subscription",
            outcome="escalated",
            esc=True,
            halluc=False,
            sentiment="negative",
            quality=80,
        )
        expected = {
            "intent_contains": "cancel",
            "outcome": "resolved",
            "escalation_signal": False,
        }
        results = engine.evaluate(expected, report)
        assert len(results) == 3
        assert results[0].passed is True
        assert results[1].passed is False
        assert results[2].passed is False

    def test_empty_expected(self):
        report = _make_report()
        results = engine.evaluate({}, report)
        assert results == []
