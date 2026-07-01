"""
Layer 4: Fact Extraction & Verification — pulls concrete facts from transcript,
verifies LLM analysis doesn't contradict them.
"""

import re
from pydantic import BaseModel
from utils.logger import logger


class Fact(BaseModel):
    text: str
    fact_type: str = "general"  # name, number, date, promise, action
    value: str = ""


class FactVerificationResult(BaseModel):
    accuracy: float = 1.0
    facts_found: list[Fact] = []
    contradictions: list[str] = []


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
        """Verify analysis doesn't contradict transcript facts."""
        facts = self.extract_facts(transcript)
        contradictions = []

        analysis_text = str(analysis).lower()

        for fact in facts:
            if fact.fact_type == "number":
                # Check if analysis mentions a different number
                numbers_in_analysis = re.findall(r"\$?\d[\d,]*\.?\d*", analysis_text)
                if numbers_in_analysis:
                    fact_num = fact.value.replace("$", "").replace(",", "")
                    for analysis_num in numbers_in_analysis:
                        analysis_num_clean = analysis_num.replace("$", "").replace(",", "")
                        try:
                            if abs(float(fact_num) - float(analysis_num_clean)) > 0.01:
                                if analysis_num_clean in analysis_text:
                                    contradictions.append(
                                        f"transcript says {fact.value} but analysis mentions {analysis_num}"
                                    )
                        except ValueError:
                            pass

            elif fact.fact_type == "promise":
                # Check if analysis claims something was promised when it wasn't, or vice versa
                promise_keywords = ["promise", "guarantee", "commit", "will do"]
                has_promise_in_transcript = any(kw in fact.text.lower() for kw in promise_keywords)
                has_promise_in_analysis = any(kw in analysis_text for kw in promise_keywords)
                if has_promise_in_transcript and "no promise" in analysis_text:
                    contradictions.append(f"transcript contains promise but analysis says none")
                if not has_promise_in_transcript and "promise" in analysis_text and "no" not in analysis_text:
                    contradictions.append(f"analysis claims promise but none found in transcript")

        accuracy = 1.0 - (len(contradictions) / max(len(facts), 1))

        return FactVerificationResult(
            accuracy=round(accuracy, 4),
            facts_found=facts,
            contradictions=contradictions,
        )
