from dataclasses import dataclass
from typing import Any


@dataclass
class AssertionResult:
    field: str
    expected: Any
    actual: Any
    passed: bool
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "message": self.message,
        }


class AssertionEngine:
    def evaluate(self, expected: dict, report: dict) -> list[AssertionResult]:
        results: list[AssertionResult] = []
        analysis = report.get("analysis") or {}
        report_data = report.get("report") or {}

        if "intent_contains" in expected:
            actual_intent = analysis.get("intent", "")
            exp = expected["intent_contains"]
            passed = exp.lower() in actual_intent.lower() if actual_intent else False
            msg = "" if passed else f"intent '{actual_intent}' does not contain '{exp}'"
            results.append(AssertionResult("intent_contains", exp, actual_intent, passed, msg))

        if "outcome" in expected:
            actual = analysis.get("outcome")
            passed = expected["outcome"] == actual
            msg = "" if passed else f"expected outcome '{expected['outcome']}', got '{actual}'"
            results.append(AssertionResult("outcome", expected["outcome"], actual, passed, msg))

        if "escalation_signal" in expected:
            actual = analysis.get("escalation_signal")
            passed = expected["escalation_signal"] is actual
            msg = (
                ""
                if passed
                else f"expected escalation_signal={expected['escalation_signal']}, got {actual}"
            )
            results.append(
                AssertionResult(
                    "escalation_signal", expected["escalation_signal"], actual, passed, msg
                )
            )

        if "hallucination_detected" in expected:
            actual = analysis.get("hallucination_detected")
            passed = expected["hallucination_detected"] is actual
            msg = (
                ""
                if passed
                else f"expected hallucination_detected={expected['hallucination_detected']}, got {actual}"
            )
            results.append(
                AssertionResult(
                    "hallucination_detected",
                    expected["hallucination_detected"],
                    actual,
                    passed,
                    msg,
                )
            )

        if "sentiment_arc" in expected:
            actual = analysis.get("sentiment_arc")
            passed = expected["sentiment_arc"] == actual
            msg = (
                ""
                if passed
                else f"expected sentiment_arc='{expected['sentiment_arc']}', got '{actual}'"
            )
            results.append(
                AssertionResult("sentiment_arc", expected["sentiment_arc"], actual, passed, msg)
            )

        if "min_quality_score" in expected:
            actual = report_data.get("quality_score")
            exp = expected["min_quality_score"]
            passed = actual is not None and actual >= exp
            msg = "" if passed else f"quality_score {actual} < minimum {exp}"
            results.append(AssertionResult("min_quality_score", exp, actual, passed, msg))

        return results
