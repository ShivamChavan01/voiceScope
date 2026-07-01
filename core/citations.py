"""
Layer 2: Citation Verification — checks that LLM findings reference the actual transcript.
"""

import re
from difflib import SequenceMatcher
from pydantic import BaseModel


class CitationResult(BaseModel):
    coverage: float = 0.0
    matched: list[str] = []
    unmatched: list[str] = []
    total_findings: int = 0


class CitationVerifier:
    """Verify that LLM findings are grounded in the transcript."""

    FUZZY_THRESHOLD = 0.6

    def verify(self, transcript: str, findings: list[str]) -> CitationResult:
        if not transcript or not findings:
            return CitationResult(
                coverage=1.0 if not findings else 0.0,
                total_findings=len(findings),
            )

        transcript_lower = transcript.lower()
        matched = []
        unmatched = []

        for finding in findings:
            if self._is_grounded(transcript_lower, finding):
                matched.append(finding)
            else:
                unmatched.append(finding)

        coverage = len(matched) / len(findings) if findings else 0.0

        return CitationResult(
            coverage=round(coverage, 4),
            matched=matched,
            unmatched=unmatched,
            total_findings=len(findings),
        )

    def _is_grounded(self, transcript: str, finding: str) -> bool:
        """Check if a finding is grounded in the transcript."""
        finding_lower = finding.lower()

        # Direct substring match
        if finding_lower in transcript:
            return True

        # Check if significant phrases from the finding appear in transcript
        phrases = self._extract_key_phrases(finding_lower)
        if phrases:
            found_count = sum(1 for p in phrases if p in transcript)
            if found_count / len(phrases) >= 0.5:
                return True

        # Fuzzy match against transcript segments
        sentences = re.split(r"[.!?]+", transcript)
        for sentence in sentences:
            ratio = SequenceMatcher(None, finding_lower, sentence.strip()).ratio()
            if ratio >= self.FUZZY_THRESHOLD:
                return True

        return False

    def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract meaningful phrases (nouns, verbs, numbers) from text."""
        words = text.split()
        # Filter out common stop words
        stop_words = {
            "the", "a", "an", "is", "was", "were", "are", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "shall", "can", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "we", "our", "you", "your", "he", "she", "his", "her",
            "and", "but", "or", "not", "no", "so", "if", "then", "than",
            "too", "very", "just", "about", "also", "how", "what", "when",
            "where", "who", "which", "there", "here", "all", "each", "every",
        }
        phrases = []
        for i in range(len(words)):
            if words[i] not in stop_words and len(words[i]) > 2:
                phrases.append(words[i])
            if i + 1 < len(words) and words[i] not in stop_words and words[i + 1] not in stop_words:
                bigram = f"{words[i]} {words[i+1]}"
                phrases.append(bigram)
        return phrases
