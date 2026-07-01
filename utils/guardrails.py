import re
from typing import Optional
from utils.logger import logger


# Harmful content patterns
HARMFUL_PATTERNS = {
    "self_harm": [
        r"\b(kill myself|suicide|end my life|self[- ]?harm|cut myself)\b",
        r"\b(want to die|don't want to live|no reason to live)\b",
    ],
    "violence": [
        r"\b(kill|murder|assault|attack|shoot|stab|bomb)\b.*\b(someone|them|him|her|people)\b",
        r"\b(threaten|threatening|going to hurt)\b",
    ],
    "harassment": [
        r"\b(you're an idiot|you're stupid|shut up|go away|leave me alone)\b.*\b(idiot|stupid|dumb|loser)\b",
    ],
    "medical_advice": [
        r"\b(you should take|dosage|prescribe|medication for|diagnosis)\b",
        r"\b(I recommend you take|the cure for|treatment is)\b",
    ],
    "financial_advice": [
        r"\b(you should invest|buy (stocks|crypto)|guaranteed returns|financial advice)\b",
    ],
}

# PII patterns for redaction
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(\+?1?[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}


class GuardrailResult:
    def __init__(self):
        self.blocked = False
        self.block_reason: Optional[str] = None
        self.flagged_categories: list[str] = []
        self.redacted_text: Optional[str] = None
        self.warnings: list[str] = []


class ContentGuardrails:
    """Content guardrails — detects harmful content and redacts PII."""

    def __init__(self):
        self.enabled_categories = set(HARMFUL_PATTERNS.keys())
        self.pii_redaction_enabled = True

    def check_input(self, text: str) -> GuardrailResult:
        """Check user input for harmful content."""
        result = GuardrailResult()
        text_lower = text.lower()

        for category, patterns in HARMFUL_PATTERNS.items():
            if category not in self.enabled_categories:
                continue
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    result.flagged_categories.append(category)
                    result.blocked = True
                    result.block_reason = f"Input contains {category.replace('_', ' ')} content"
                    logger.warning(f"[Guardrails] blocked input: category={category}")
                    return result

        return result

    def check_output(self, text: str) -> GuardrailResult:
        """Check agent output for harmful content before speaking."""
        result = GuardrailResult()
        text_lower = text.lower()

        for category, patterns in HARMFUL_PATTERNS.items():
            if category not in self.enabled_categories:
                continue
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    result.flagged_categories.append(category)
                    result.blocked = True
                    result.block_reason = f"Output contains {category.replace('_', ' ')} content"
                    result.redacted_text = "[Content filtered by guardrails]"
                    logger.warning(f"[Guardrails] blocked output: category={category}")
                    return result

        return result

    def redact_pii(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Redact PII from text. Returns (redacted_text, list_of_redactions)."""
        redacted = text
        redactions = []

        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, redacted)
            for match in matches:
                redacted = redacted.replace(match, f"[REDACTED_{pii_type.upper()}]")
                redactions.append({"type": pii_type, "original": match})

        return redacted, redactions

    def set_categories(self, categories: list[str]):
        """Enable/disable specific guardrail categories."""
        self.enabled_categories = set(categories)

    def get_status(self) -> dict:
        return {
            "enabled_categories": list(self.enabled_categories),
            "pii_redaction": self.pii_redaction_enabled,
            "total_patterns": sum(len(p) for p in HARMFUL_PATTERNS.values()),
        }


# Global instance
guardrails = ContentGuardrails()
