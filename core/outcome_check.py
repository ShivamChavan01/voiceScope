"""
Layer 6 & 7: Outcome Evidence Check + Escalation Signal Verification.
Verifies LLM outcome/escalation labels have supporting evidence in transcript.
"""

from pydantic import BaseModel


class OutcomeCheckResult(BaseModel):
    has_evidence: bool = True
    evidence_score: float = 1.0
    evidence_found: list[str] = []
    missing_evidence: str = ""


class OutcomeCheck:
    """Verify outcome and escalation labels against transcript evidence."""

    RESOLUTION_MARKERS = [
        "resolved", "fixed", "solved", "completed", "done", "closed",
        "all set", "taken care of", "handled", "confirmed", "processed",
        "shipped", "delivered", "refunded", "credited", "updated",
        "you're welcome", "glad to help", "anything else",
    ]

    UNRESOLVED_MARKERS = [
        "not sure", "don't know", "can't help", "unable to", "doesn't work",
        "still broken", "still not", "hasn't been", "waiting", "pending",
        "needs to", "have to", "must", "will need", "follow up",
    ]

    ESCALATION_MARKERS = [
        "transfer", "manager", "supervisor", "escalate", "higher level",
        "specialist", "team lead", "director", "put you through",
        "let me connect you", "forward your call", "file a complaint",
        "formal complaint", "report this", "legal", "attorney",
    ]

    def check(self, transcript: str, outcome: str) -> OutcomeCheckResult:
        """Check if outcome label has evidence in transcript."""
        transcript_lower = transcript.lower()
        outcome_lower = outcome.lower()

        if outcome_lower == "resolved":
            found = [m for m in self.RESOLUTION_MARKERS if m in transcript_lower]
            return OutcomeCheckResult(
                has_evidence=len(found) > 0,
                evidence_score=min(1.0, len(found) * 0.2),
                evidence_found=found[:10],
                missing_evidence="" if found else "no resolution markers found in transcript",
            )
        elif outcome_lower == "unresolved":
            found = [m for m in self.UNRESOLVED_MARKERS if m in transcript_lower]
            return OutcomeCheckResult(
                has_evidence=len(found) > 0,
                evidence_score=min(1.0, len(found) * 0.25),
                evidence_found=found[:10],
                missing_evidence="" if found else "no unresolved markers found in transcript",
            )
        elif outcome_lower == "escalated":
            found = [m for m in self.ESCALATION_MARKERS if m in transcript_lower]
            return OutcomeCheckResult(
                has_evidence=len(found) > 0,
                evidence_score=min(1.0, len(found) * 0.25),
                evidence_found=found[:10],
                missing_evidence="" if found else "no escalation markers found in transcript",
            )
        else:
            return OutcomeCheckResult(
                has_evidence=True,
                evidence_score=0.5,
                missing_evidence=f"unknown outcome type: {outcome}",
            )

    def check_escalation(self, transcript: str, escalation_signal: bool) -> OutcomeCheckResult:
        """Specifically verify escalation signal against transcript."""
        if not escalation_signal:
            return OutcomeCheckResult(has_evidence=True, evidence_score=1.0)

        transcript_lower = transcript.lower()
        found = [m for m in self.ESCALATION_MARKERS if m in transcript_lower]

        return OutcomeCheckResult(
            has_evidence=len(found) > 0,
            evidence_score=min(1.0, len(found) * 0.25),
            evidence_found=found[:10],
            missing_evidence="" if found else "escalation_signal=True but no markers found",
        )
