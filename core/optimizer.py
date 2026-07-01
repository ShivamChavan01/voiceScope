"""
Calibration Optimizer — auto-tunes harness layer weights based on benchmark results.
Tracks which layers actually catch errors vs which are noise.
"""

import json
import os
import time
from pathlib import Path
from pydantic import BaseModel, Field
from utils.logger import logger


class LayerPerformance(BaseModel):
    name: str
    accuracy: float = 0.0
    weight: float = 0.1
    samples: int = 0
    false_positives: int = 0
    false_negatives: int = 0


class OptimizationResult(BaseModel):
    old_weights: dict[str, float] = Field(default_factory=dict)
    new_weights: dict[str, float] = Field(default_factory=dict)
    improvement: float = 0.0
    changes_made: list[str] = Field(default_factory=list)


class CalibrationOptimizer:
    """Auto-tune harness weights based on observed accuracy."""

    DEFAULT_WEIGHTS = {
        "schema": 0.30,
        "citations": 0.15,
        "facts": 0.15,
        "sentiment_consistency": 0.10,
        "outcome_evidence": 0.10,
        "escalation": 0.05,
        "duplicate": 0.05,
        "cross_check": 0.10,
    }

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or os.getenv("OPTIMIZER_DB_PATH", "./optimizer.json")
        self._history: list[dict] = []
        self._load()

    def _load(self):
        path = Path(self.db_path)
        if path.exists():
            try:
                self._history = json.loads(path.read_text())
            except Exception:
                self._history = []

    def _save(self):
        path = Path(self.db_path)
        try:
            path.write_text(json.dumps(self._history, indent=2))
        except Exception as e:
            logger.warning(f"[Optimizer] failed to save: {e}")

    def optimize(self, benchmark_results: list[dict]) -> OptimizationResult:
        """Tune weights based on benchmark results."""
        old_weights = dict(self.DEFAULT_WEIGHTS)
        if self._history:
            old_weights = self._history[-1].get("weights", self.DEFAULT_WEIGHTS)

        # Compute per-layer accuracy from benchmark results
        layer_stats: dict[str, dict] = {}
        for result in benchmark_results:
            for layer, score in result.get("layer_scores", {}).items():
                if layer not in layer_stats:
                    layer_stats[layer] = {"scores": [], "fp": 0, "fn": 0}
                layer_stats[layer]["scores"].append(score)

        # Calculate new weights proportional to accuracy
        new_weights = {}
        total_acc = 0
        for layer, stats in layer_stats.items():
            avg_acc = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0.5
            new_weights[layer] = avg_acc
            total_acc += avg_acc

        # Normalize to sum to 1.0
        if total_acc > 0:
            for layer in new_weights:
                new_weights[layer] = round(new_weights[layer] / total_acc, 4)

        # Keep layers not in benchmark at their old weights
        for layer, weight in old_weights.items():
            if layer not in new_weights:
                new_weights[layer] = weight

        # Ensure minimum weight for critical layers
        for layer in ["schema", "citations"]:
            if layer in new_weights and new_weights[layer] < 0.05:
                new_weights[layer] = 0.05

        # Re-normalize
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

        # Track changes
        changes = []
        for layer in set(list(old_weights.keys()) + list(new_weights.keys())):
            old_w = old_weights.get(layer, 0)
            new_w = new_weights.get(layer, 0)
            if abs(old_w - new_w) > 0.01:
                changes.append(f"{layer}: {old_w:.3f} → {new_w:.3f}")

        # Compute improvement estimate
        old_score = sum(old_weights.get(l, 0) * s for l, s in layer_stats.items()
                        for s in [sum(layer_stats[l]["scores"]) / max(len(layer_stats[l]["scores"]), 1)])
        new_score = sum(new_weights.get(l, 0) * s for l, s in layer_stats.items()
                        for s in [sum(layer_stats[l]["scores"]) / max(len(layer_stats[l]["scores"]), 1)])
        improvement = new_score - old_score

        # Save to history
        self._history.append({
            "timestamp": time.time(),
            "weights": new_weights,
            "improvement": improvement,
            "changes": changes,
        })
        if len(self._history) % 5 == 0:
            self._save()

        return OptimizationResult(
            old_weights=old_weights,
            new_weights=new_weights,
            improvement=round(improvement, 4),
            changes_made=changes,
        )

    def get_current_weights(self) -> dict[str, float]:
        if self._history:
            return self._history[-1].get("weights", self.DEFAULT_WEIGHTS)
        return self.DEFAULT_WEIGHTS

    def get_history(self) -> list[dict]:
        return self._history
