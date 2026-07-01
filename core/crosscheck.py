"""
Layer 3: Cross-Check — runs analysis twice with different prompts, compares results.
"""

import os
import json
from typing import Optional
from pydantic import BaseModel
from utils.logger import logger


class CrossCheckResult(BaseModel):
    agreement_rate: float = 0.0
    disagreements: list[str] = []
    checked: bool = False


class CrossChecker:
    """Cross-check analysis by running it again with a different prompt."""

    def __init__(self):
        self.enabled = os.getenv("CROSS_CHECK_ENABLED", "false").lower() == "true"

    async def check(self, transcript: str, original_analysis: dict, provider=None) -> CrossCheckResult:
        if not self.enabled or not provider:
            return CrossCheckResult(checked=False)

        try:
            prompt = self._build_crosscheck_prompt(transcript, original_analysis)
            response = await provider.complete(
                prompt=prompt,
                temperature=0.5,  # Different temp for diversity
                response_format={"type": "json_object"},
            )
            second_analysis = json.loads(response.content)
            return self._compare(original_analysis, second_analysis)
        except Exception as e:
            logger.warning(f"[CrossCheck] failed: {e}")
            return CrossCheckResult(checked=False)

    def _build_crosscheck_prompt(self, transcript: str, original: dict) -> str:
        return f"""You are verifying an analysis of this voice call transcript.

TRANSCRIPT:
{transcript[:3000]}

ORIGINAL ANALYSIS:
{json.dumps(original, indent=2)}

Verify each claim. Return JSON:
{{
  "sentiment_agrees": true/false,
  "outcome_agrees": true/false,
  "hallucination_flag_agrees": true/false,
  "disagreements": ["list any specific disagreements"],
  "verification_notes": "brief explanation"
}}"""

    def _compare(self, original: dict, second: dict) -> CrossCheckResult:
        disagreements = []

        fields_to_check = ["sentiment_arc", "outcome", "hallucination_detected"]
        agree_count = 0
        total = 0

        for field in fields_to_check:
            orig_val = original.get(field)
            second_val = second.get(field)
            total += 1
            if orig_val == second_val:
                agree_count += 1
            else:
                disagreements.append(
                    f"{field}: original={orig_val}, cross_check={second_val}"
                )

        # Check if cross-check also flagged disagreements with the analysis
        if second.get("disagreements"):
            for d in second["disagreements"]:
                if d not in disagreements:
                    disagreements.append(f"cross_check_notes: {d}")

        agreement_rate = agree_count / total if total > 0 else 0.0

        return CrossCheckResult(
            agreement_rate=round(agreement_rate, 4),
            disagreements=disagreements,
            checked=True,
        )
