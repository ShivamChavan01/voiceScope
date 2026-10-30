"""
Layer 4: Fact Extraction & Verification — pulls concrete facts from transcript,
verifies LLM analysis doesn't contradict them.
"""

import re

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Fact(BaseModel):
    text: str
    fact_type: str = "general"  # name, number, date, promise, action
    value: str = ""


class FactVerificationResult(BaseModel):
    # Numeric support checks analysis claims, not the caller agent's truthfulness.
    accuracy: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Literal["assessed", "not_assessed"] = "not_assessed"
    claims_checked: int = 0
    facts_found: list[Fact] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class FactExtractor:
    """Extract concrete facts from transcript and verify against analysis."""

    # Patterns for common facts
    NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*\.?\d*")
    DATE_PATTERN = re.compile(
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{1,2}(?:,?\s*\d{4})?\b",
        re.IGNORECASE,
    )
    PROMISE_PATTERNS = [
        re.compile(r"i(?:'ll| will) (.{10,60})", re.IGNORECASE),
        re.compile(r"we(?:'ll| will) (.{10,60})", re.IGNORECASE),
        re.compile(r"(?:promise|guarantee|commit) (?:to |that )(.{10,60})", re.IGNORECASE),
    ]
    ACTION_PATTERNS = [
        re.compile(r"(?:send|email|call|process|refund|cancel|update|fix) (?:you |the )?(.{5,60})", re.IGNORECASE),
    ]

    def extract_facts(self, transcript: str) -> list[Fact]:
        """Extract concrete facts from transcript."""
        facts = []

        # Extract numbers
        for match in self.NUMBER_PATTERN.finditer(transcript):
            facts.append(Fact(text=match.group(), fact_type="number", value=match.group()))

        # Extract dates
        for match in self.DATE_PATTERN.finditer(transcript):
            facts.append(Fact(text=match.group(), fact_type="date", value=match.group()))

        # Extract promises
        for pattern in self.PROMISE_PATTERNS:
            for match in pattern.finditer(transcript):
                facts.append(Fact(text=match.group(), fact_type="promise", value=match.group(1).strip()))

        # Extract actions
        for pattern in self.ACTION_PATTERNS:
            for match in pattern.finditer(transcript):
                facts.append(Fact(text=match.group(), fact_type="action", value=match.group(1).strip()))

        return facts

    def verify(self, transcript: str, analysis: dict) -> FactVerificationResult:
        """Measure numeric support in findings, once per distinct claimed value.

        A number absent from a transcript is unsupported, not a proven contradiction.
        Matching values do not prove semantic correctness (price vs. refund, negation,
        speaker attribution). Policy excerpts and model metadata are not call claims.
        """
        facts = self.extract_facts(transcript)
        if not transcript.strip():
            return FactVerificationResult(facts_found=facts)

        def values(text: str) -> set[tuple[bool, Decimal]]:
            return {
                (match.group().startswith("$"), Decimal(match.group().lstrip("$").replace(",", "")))
                for match in self.NUMBER_PATTERN.finditer(text)
            }

        findings = analysis.get("findings", [])
        claims = set()
        if isinstance(findings, list):
            for finding in findings:
                if isinstance(finding, str):
                    claims.update(values(finding))
        if not claims:
            return FactVerificationResult(facts_found=facts)

        observed = values(transcript)
        unsupported = claims - observed
        return FactVerificationResult(
            status="assessed",
            claims_checked=len(claims),
            accuracy=round(len(claims & observed) / len(claims), 4),
            facts_found=facts,
            unsupported_claims=[
                f"analysis numeric claim {'$' if currency else ''}{number} is absent from transcript"
                for currency, number in sorted(unsupported)
            ],
        )
