"""
Prompt Improvement Tracker — tracks which prompts produce the best results
and suggests improvements based on common failure patterns.
"""

import json
import os
import time
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
from utils.logger import logger


class PromptRecord(BaseModel):
    prompt_name: str
    version: int = 1
    accuracy: float = 0.0
    total_runs: int = 0
    failure_patterns: list[str] = Field(default_factory=list)
    created_at: float = 0.0


class FailurePattern(BaseModel):
    pattern: str
    count: int = 0
    last_seen: float = 0.0
    suggestion: str = ""


class PromptTracker:
    """Track prompt performance and suggest improvements."""

    def __init__(self, db_path: str = ""):
        data_dir = os.environ.get("DATA_DIR", ".")
        self.db_path = db_path or os.getenv("PROMPT_TRACKER_DB_PATH", str(Path(data_dir) / "prompt_tracker.json"))
        self._records: list[PromptRecord] = []
        self._patterns: list[FailurePattern] = []
        self._load()

    def _load(self):
        path = Path(self.db_path)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._records = [PromptRecord(**r) for r in data.get("records", [])]
                self._patterns = [FailurePattern(**p) for p in data.get("patterns", [])]
            except Exception:
                pass

    def _save(self):
        path = Path(self.db_path)
        try:
            path.write_text(json.dumps({
                "records": [r.model_dump() for r in self._records],
                "patterns": [p.model_dump() for p in self._patterns],
            }, indent=2))
        except Exception as e:
            logger.warning(f"[PromptTracker] failed to save: {e}")

    def record_run(self, prompt_name: str, accuracy: float, errors: Optional[list[str]] = None):
        """Record a prompt execution result."""
        existing = next((r for r in self._records if r.prompt_name == prompt_name), None)
        if existing:
            existing.total_runs += 1
            # Running average accuracy
            existing.accuracy = (existing.accuracy * (existing.total_runs - 1) + accuracy) / existing.total_runs
            if errors:
                for error in errors:
                    if error not in existing.failure_patterns:
                        existing.failure_patterns.append(error)
        else:
            self._records.append(PromptRecord(
                prompt_name=prompt_name,
                accuracy=accuracy,
                total_runs=1,
                failure_patterns=errors or [],
                created_at=time.time(),
            ))

        # Track failure patterns
        if errors:
            for error in errors:
                pattern = self._categorize_error(error)
                existing_pattern = next((p for p in self._patterns if p.pattern == pattern), None)
                if existing_pattern:
                    existing_pattern.count += 1
                    existing_pattern.last_seen = time.time()
                else:
                    self._patterns.append(FailurePattern(
                        pattern=pattern,
                        count=1,
                        last_seen=time.time(),
                        suggestion=self._suggest_fix(pattern),
                    ))

    def get_suggestions(self) -> list[dict]:
        """Get improvement suggestions based on failure patterns."""
        suggestions = []
        for pattern in sorted(self._patterns, key=lambda p: p.count, reverse=True)[:10]:
            suggestions.append({
                "pattern": pattern.pattern,
                "occurrences": pattern.count,
                "suggestion": pattern.suggestion,
            })
        return suggestions

    def get_prompt_stats(self) -> list[dict]:
        """Get accuracy stats per prompt."""
        return [
            {
                "name": r.prompt_name,
                "accuracy": round(r.accuracy, 4),
                "total_runs": r.total_runs,
                "failure_count": len(r.failure_patterns),
            }
            for r in sorted(self._records, key=lambda r: r.accuracy)
        ]

    def _categorize_error(self, error: str) -> str:
        """Categorize an error string into a pattern."""
        error_lower = error.lower()
        if "sentiment" in error_lower:
            return "sentiment_mismatch"
        elif "outcome" in error_lower:
            return "outcome_mismatch"
        elif "escalation" in error_lower:
            return "escalation_mismatch"
        elif "citation" in error_lower or "unmatched" in error_lower:
            return "citation_failure"
        elif "contradiction" in error_lower:
            return "fact_contradiction"
        elif "duplicate" in error_lower:
            return "duplicate_detected"
        elif "schema" in error_lower:
            return "schema_violation"
        else:
            return f"other: {error[:50]}"

    def _suggest_fix(self, pattern: str) -> str:
        """Suggest a fix based on the error pattern."""
        suggestions = {
            "sentiment_mismatch": "Review sentiment analysis prompt. Add more explicit examples of negative/positive cues.",
            "outcome_mismatch": "Outcome classification prompt may need clearer definitions. Add examples of resolved vs unresolved vs escalated.",
            "escalation_mismatch": "Escalation detection prompt needs more markers. Include 'transfer', 'manager', 'supervisor' as key signals.",
            "citation_failure": "Findings are not grounded in transcript. Strengthen citation requirements in the prompt.",
            "fact_contradiction": "LLM is contradicting transcript facts. Add explicit instruction to only use information from the transcript.",
            "duplicate_detected": "Same analysis repeated. Consider adding more diversity to the prompt or varying temperature.",
            "schema_violation": "LLM output doesn't match expected schema. Add stricter format instructions or use structured output.",
        }
        return suggestions.get(pattern, "Review the prompt and add more explicit instructions for this case.")
