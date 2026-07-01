"""
Layer 13: Feedback Loop — endpoint for users to mark results as correct/incorrect.
Feeds back into confidence calibration (Layer 12).
"""

from pydantic import BaseModel
from utils.logger import logger


class FeedbackEntry(BaseModel):
    run_id: str
    feedback: str  # "correct" or "incorrect"
    notes: str = ""


class FeedbackStore:
    """Store user feedback for harness calibration."""

    def __init__(self):
        from core.calibration import ConfidenceCalibrator
        self.calibrator = ConfidenceCalibrator()

    def submit(self, run_id: str, feedback: str, notes: str = "") -> dict:
        if feedback not in ("correct", "incorrect"):
            raise ValueError(f"feedback must be 'correct' or 'incorrect', got '{feedback}'")

        self.calibrator.add_feedback(run_id, feedback)

        logger.info(f"[Feedback] run_id={run_id} feedback={feedback}")

        return {
            "run_id": run_id,
            "feedback": feedback,
            "status": "recorded",
            "calibration": self.calibrator.get_calibration().model_dump(),
        }

    def get_calibration(self) -> dict:
        return dict(self.calibrator.get_calibration().model_dump())
