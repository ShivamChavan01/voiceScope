"""
Layer 12: Confidence Calibration — track whether harness confidence correlates with accuracy.
Layer 13: Feedback Loop — accept user feedback to improve calibration.
"""

import os
import json
import time
from pathlib import Path
from pydantic import BaseModel
from utils.logger import logger


class CalibrationEntry(BaseModel):
    timestamp: float = 0.0
    truth_score: float = 0.0
    confidence: str = ""
    user_feedback: str = ""  # "correct", "incorrect", ""
    run_id: str = ""


class CalibrationResult(BaseModel):
    total_predictions: int = 0
    high_confidence_accuracy: float = 0.0
    medium_confidence_accuracy: float = 0.0
    low_confidence_accuracy: float = 0.0
    calibration_error: float = 0.0  # Brier-like score
    feedback_count: int = 0


class ConfidenceCalibrator:
    """Track calibration between harness confidence and actual accuracy."""

    def __init__(self, db_path: str = ""):
        data_dir = os.environ.get("DATA_DIR", ".")
        self.db_path = db_path or os.getenv("CALIBRATION_DB_PATH", str(Path(data_dir) / "calibration.json"))
        self._entries: list[CalibrationEntry] = []
        self._load()

    def _load(self):
        path = Path(self.db_path)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._entries = [CalibrationEntry(**e) for e in data]
            except Exception:
                self._entries = []

    def _save(self):
        path = Path(self.db_path)
        try:
            path.write_text(json.dumps([e.model_dump() for e in self._entries], indent=2))
        except Exception as e:
            logger.warning(f"[Calibration] failed to save: {e}")

    def record(self, run_id: str, truth_score: float, confidence: str):
        entry = CalibrationEntry(
            timestamp=time.time(),
            truth_score=truth_score,
            confidence=confidence,
            run_id=run_id,
        )
        self._entries.append(entry)
        if len(self._entries) % 10 == 0:
            self._save()

    def add_feedback(self, run_id: str, feedback: str):
        for entry in reversed(self._entries):
            if entry.run_id == run_id:
                entry.user_feedback = feedback
                break
        self._save()

    def get_calibration(self) -> CalibrationResult:
        if not self._entries:
            return CalibrationResult()

        with_feedback = [e for e in self._entries if e.user_feedback]
        high = [e for e in with_feedback if e.confidence == "high"]
        medium = [e for e in with_feedback if e.confidence == "medium"]
        low = [e for e in with_feedback if e.confidence == "low"]

        def accuracy(entries):
            if not entries:
                return 0.0
            correct = sum(1 for e in entries if e.user_feedback == "correct")
            return correct / len(entries)

        # Brier-like calibration error
        errors = []
        for e in with_feedback:
            predicted = {"high": 0.9, "medium": 0.7, "low": 0.5, "very_low": 0.3}.get(e.confidence, 0.5)
            actual = 1.0 if e.user_feedback == "correct" else 0.0
            errors.append((predicted - actual) ** 2)
        brier = sum(errors) / len(errors) if errors else 0.0

        return CalibrationResult(
            total_predictions=len(self._entries),
            high_confidence_accuracy=round(accuracy(high), 4),
            medium_confidence_accuracy=round(accuracy(medium), 4),
            low_confidence_accuracy=round(accuracy(low), 4),
            calibration_error=round(brier, 4),
            feedback_count=len(with_feedback),
        )
