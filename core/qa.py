import sqlite3
import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from utils.logger import logger


class ResolutionCriterion(BaseModel):
    name: str
    description: str
    weight: float = 1.0
    metric_type: str = "ai_evaluated"  # ai_evaluated | hallucination_rate | sentiment | quality_score


class QACohort(BaseModel):
    name: str
    agent_filter: Optional[str] = None
    platform_filter: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    sampling_pct: float = 10.0
    weekly_max: int = 100
    criteria: list[ResolutionCriterion] = Field(default_factory=list)


class QAStore:
    """QA cohort system — sampling, weighted scoring, resolution criteria."""

    def __init__(self):
        data_dir = os.environ.get("DATA_DIR", ".")
        self.db_path = os.getenv("QA_DB_PATH", str(Path(data_dir) / "qa.db"))
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_cohorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                agent_filter TEXT,
                platform_filter TEXT,
                min_duration REAL,
                max_duration REAL,
                sampling_pct REAL DEFAULT 10.0,
                weekly_max INTEGER DEFAULT 100,
                criteria_json TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cohort_id INTEGER NOT NULL,
                run_id TEXT NOT NULL,
                overall_score REAL,
                passed INTEGER DEFAULT 0,
                criteria_scores_json TEXT DEFAULT '{}',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cohort_id) REFERENCES qa_cohorts(id)
            )
        """)
        self._conn.commit()
        logger.info(f"[QAStore] initialized db={self.db_path}")

    async def create_cohort(self, cohort: QACohort) -> int:
        cursor = self._conn.execute(
            """INSERT INTO qa_cohorts (name, agent_filter, platform_filter, min_duration, max_duration, sampling_pct, weekly_max, criteria_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cohort.name,
                cohort.agent_filter,
                cohort.platform_filter,
                cohort.min_duration,
                cohort.max_duration,
                cohort.sampling_pct,
                cohort.weekly_max,
                json.dumps([c.model_dump() for c in cohort.criteria]),
            ),
        )
        self._conn.commit()
        cohort_id = cursor.lastrowid
        logger.info(f"[QAStore] created cohort id={cohort_id} name={cohort.name}")
        return int(cohort_id)

    async def list_cohorts(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM qa_cohorts ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["criteria"] = json.loads(d["criteria_json"])
            del d["criteria_json"]
            result.append(d)
        return result

    async def score_call(self, cohort_id: int, run_id: str, metrics: dict) -> dict:
        """Score a call against cohort criteria. Returns score breakdown."""
        cohort = self._conn.execute(
            "SELECT * FROM qa_cohorts WHERE id = ?", (cohort_id,)
        ).fetchone()
        if not cohort:
            raise ValueError(f"Cohort {cohort_id} not found")

        criteria = json.loads(cohort["criteria_json"])
        scores = {}
        total_weight = 0
        weighted_sum = 0

        for criterion in criteria:
            name = criterion["name"]
            weight = criterion.get("weight", 1.0)
            metric_type = criterion.get("metric_type", "ai_evaluated")
            total_weight += weight

            score = self._evaluate_criterion(metric_type, criterion, metrics)
            scores[name] = {
                "score": score,
                "weight": weight,
                "passed": score >= 0.7,
            }
            weighted_sum += score * weight

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        passed = overall >= 0.7

        self._conn.execute(
            """INSERT INTO qa_results (cohort_id, run_id, overall_score, passed, criteria_scores_json)
               VALUES (?, ?, ?, ?, ?)""",
            (cohort_id, run_id, round(overall, 4), 1 if passed else 0, json.dumps(scores)),
        )
        self._conn.commit()

        return {
            "run_id": run_id,
            "cohort_id": cohort_id,
            "overall_score": round(overall, 4),
            "passed": passed,
            "criteria": scores,
        }

    def _evaluate_criterion(self, metric_type: str, criterion: dict, metrics: dict) -> float:
        """Evaluate a single criterion against call metrics. Returns 0.0-1.0."""
        if metric_type == "hallucination_rate":
            detected = metrics.get("hallucination_detected", False)
            return 0.0 if detected else 1.0

        elif metric_type == "sentiment":
            arc = metrics.get("sentiment_arc", "")
            if any(neg in arc.lower() for neg in ["negative", "angry", "frustrated", "hostile"]):
                return 0.3
            elif any(pos in arc.lower() for pos in ["positive", "satisfied", "happy"]):
                return 1.0
            return 0.6

        elif metric_type == "quality_score":
            score = metrics.get("quality_score")
            if score is None:
                return 0.5
            return float(min(1.0, max(0.0, score / 100.0)))

        elif metric_type == "outcome":
            outcome = metrics.get("outcome", "")
            if outcome == "resolved":
                return 1.0
            elif outcome == "escalated":
                return 0.5
            return 0.3

        # Default: ai_evaluated — use quality_score as proxy
        return 0.5

    async def get_cohort_results(self, cohort_id: int, limit: int = 100) -> dict:
        """Get aggregated results for a cohort."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            results = conn.execute(
                """SELECT * FROM qa_results
                   WHERE cohort_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (cohort_id, limit),
            ).fetchall()

            summary = conn.execute(
                """SELECT
                    COUNT(*) as total,
                    AVG(overall_score) as avg_score,
                    SUM(passed) as passed_count
                FROM qa_results WHERE cohort_id = ?""",
                (cohort_id,),
            ).fetchone()

        total = summary["total"] if summary else 0
        passed = summary["passed_count"] if summary else 0

        return {
            "cohort_id": cohort_id,
            "total_scored": total,
            "avg_score": round(summary["avg_score"], 4) if summary and summary["avg_score"] else 0.0,
            "pass_rate": round(passed / total, 4) if total > 0 else 0.0,
            "results": [dict(r) for r in results],
        }
