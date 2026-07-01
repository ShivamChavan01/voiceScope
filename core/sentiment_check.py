"""
Layer 5: Sentiment Consistency Check — verifies LLM sentiment matches transcript cues.
"""

from pydantic import BaseModel


class SentimentCheckResult(BaseModel):
    consistent: bool = True
    consistency_score: float = 1.0
    suggested_sentiment: str = ""
    cues_found: list[str] = []


class SentimentCheck:
    """Check if LLM sentiment label is consistent with transcript content."""

    NEGATIVE_CUES = [
        "angry", "furious", "frustrated", "annoyed", "irritated", "upset",
        "terrible", "horrible", "awful", "worst", "hate", "disgusted",
        "unacceptable", "ridiculous", "absurd", "outrageous",
        "disappointed", "let down", "failed", "broken", "wrong",
        "never again", "waste of time", "cancel", "refund", "escalate",
        "manager", "supervisor", "complaint", "report", "lawsuit",
    ]

    POSITIVE_CUES = [
        "great", "excellent", "amazing", "wonderful", "fantastic", "love",
        "happy", "satisfied", "pleased", "thank", "grateful", "appreciate",
        "helpful", "perfect", "awesome", "brilliant", "outstanding",
        "recommend", "best", "impressed", "fast", "quick", "easy",
        "resolved", "fixed", "solved", "working", "all set",
    ]

    NEUTRAL_CUES = [
        "okay", "fine", "alright", "understood", "noted", "sure",
        "will do", "got it", "i see", "right", "yes", "no",
        "maybe", "possibly", "perhaps", "depends",
    ]

    def check(self, transcript: str, llm_sentiment: str) -> SentimentCheckResult:
        """Check if LLM sentiment matches transcript cues."""
        transcript_lower = transcript.lower()

        neg_count = sum(1 for cue in self.NEGATIVE_CUES if cue in transcript_lower)
        pos_count = sum(1 for cue in self.POSITIVE_CUES if cue in transcript_lower)
        neu_count = sum(1 for cue in self.NEUTRAL_CUES if cue in transcript_lower)

        # Determine suggested sentiment from cues
        scores = {
            "negative": neg_count,
            "positive": pos_count,
            "neutral": neu_count,
        }
        suggested = max(scores, key=scores.get)
        total_cues = neg_count + pos_count + neu_count

        cues_found = []
        if neg_count > 0:
            cues_found.extend([f"-{c}" for c in self.NEGATIVE_CUES if c in transcript_lower])
        if pos_count > 0:
            cues_found.extend([f"+{c}" for c in self.POSITIVE_CUES if c in transcript_lower])

        # Compare
        llm_sentiment_lower = llm_sentiment.lower()
        if llm_sentiment_lower == suggested:
            consistent = True
            score = 1.0
        elif llm_sentiment_lower in scores and suggested in scores:
            # Both are valid sentiments but differ
            diff = abs(scores[llm_sentiment_lower] - scores[suggested])
            consistent = diff <= 2
            score = max(0.0, 1.0 - (diff / max(total_cues, 1)))
        else:
            # LLM returned something not in our expected set
            consistent = False
            score = 0.5

        return SentimentCheckResult(
            consistent=consistent,
            consistency_score=round(score, 4),
            suggested_sentiment=suggested,
            cues_found=cues_found[:20],  # cap at 20
        )
