"""
Layer 3: Cross-Check — validates internal consistency of analysis output.
Checks for contradictions between analysis fields themselves.
"""

from pydantic import BaseModel


class CrossCheckResult(BaseModel):
    consistent: bool = True
    inconsistencies: list[str] = []
    score: float = 1.0


class CrossChecker:
    """Check analysis output for internal contradictions."""

    def check(self, analysis: dict) -> CrossCheckResult:
        inconsistencies = []

        hallucination = analysis.get("hallucination_detected", False)
        escalation = analysis.get("escalation_signal", False)
        findings = analysis.get("findings", [])
        quality_score = analysis.get("quality_score")

        if not hallucination and analysis.get("hallucination_evidence"):
            inconsistencies.append("hallucination flag is false but hallucination evidence is present")
        if hallucination and not analysis.get("hallucination_evidence"):
            inconsistencies.append("hallucination flag is true but supporting evidence is missing")

        # Hallucination detected but no findings to base it on
        if hallucination and not findings:
            inconsistencies.append(
                "hallucination_detected=True but findings list is empty — cannot verify"
            )

        # High quality score with hallucination is contradictory
        if hallucination and quality_score is not None and quality_score >= 80:
            inconsistencies.append(
                f"quality_score={quality_score} but hallucination_detected=True — contradictory"
            )

        # Very low quality score without any errors flagged
        if quality_score is not None and quality_score < 30 and not hallucination and not escalation:
            inconsistencies.append(
                f"quality_score={quality_score} but no hallucination or escalation flagged"
            )

        score = 1.0 - (len(inconsistencies) * 0.2)
        score = max(score, 0.0)

        return CrossCheckResult(
            consistent=len(inconsistencies) == 0,
            inconsistencies=inconsistencies,
            score=round(score, 4),
        )
