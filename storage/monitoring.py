import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Optional
from utils.logger import logger


class MonitoringStore:
    """Monitoring & alerting store. Tracks metrics and fires threshold-based alerts."""

    def __init__(self):
        self.db_path = os.getenv("MONITORING_DB_PATH", "./monitoring.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS call_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    platform TEXT,
                    intent TEXT,
                    sentiment_arc TEXT,
                    outcome TEXT,
                    hallucination_detected INTEGER DEFAULT 0,
                    escalation_signal INTEGER DEFAULT 0,
                    quality_score REAL,
                    cost_usd REAL DEFAULT 0.0,
                    duration_seconds REAL,
                    word_count INTEGER,
                    provider TEXT,
                    model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    comparator TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    window_minutes INTEGER DEFAULT 60,
                    enabled INTEGER DEFAULT 1,
                    notify_url TEXT,
                    notify_email TEXT,
                    last_triggered TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER NOT NULL,
                    metric_value REAL,
                    message TEXT,
                    status TEXT DEFAULT 'active',
                    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
                )
            """)
            conn.commit()
        logger.info(f"[MonitoringStore] initialized db={self.db_path}")

    async def log_call(self, result: dict):
        """Log call metrics from a pipeline result."""
        report = result.get("report", {})
        analysis = result.get("analysis", {})
        provider_data = result.get("provider", {})

        quality_score = None
        if report and isinstance(report, dict):
            quality_score = report.get("quality_score")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO call_metrics
                   (run_id, platform, intent, sentiment_arc, outcome,
                    hallucination_detected, escalation_signal, quality_score,
                    cost_usd, duration_seconds, word_count, provider, model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.get("run_id", ""),
                    result.get("platform", "direct"),
                    analysis.get("intent") if analysis else None,
                    analysis.get("sentiment_arc") if analysis else None,
                    analysis.get("outcome") if analysis else None,
                    1 if analysis and analysis.get("hallucination_detected") else 0,
                    1 if analysis and analysis.get("escalation_signal") else 0,
                    quality_score,
                    provider_data.get("cost_usd", 0.0) if provider_data else 0.0,
                    result.get("transcript_meta", {}).get("duration_seconds"),
                    result.get("transcript_meta", {}).get("word_count"),
                    provider_data.get("name") if provider_data else None,
                    provider_data.get("model") if provider_data else None,
                ),
            )
            conn.commit()
        logger.debug(f"[MonitoringStore] logged run_id={result.get('run_id')}")

    async def check_alerts(self) -> list[dict]:
        """Check all enabled alert rules and fire if thresholds exceeded."""
        triggered = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rules = conn.execute(
                "SELECT * FROM alert_rules WHERE enabled = 1"
            ).fetchall()

            for rule in rules:
                rule_dict = dict(rule)
                value = await self._evaluate_rule(conn, rule_dict)
                if value is not None:
                    triggered.append({
                        "rule_id": rule_dict["id"],
                        "rule_name": rule_dict["name"],
                        "metric": rule_dict["metric"],
                        "threshold": rule_dict["threshold"],
                        "actual_value": value,
                        "message": f"{rule_dict['name']}: {rule_dict['metric']}={value} (threshold={rule_dict['threshold']})",
                    })
                    conn.execute(
                        """INSERT INTO alert_incidents (rule_id, metric_value, message)
                           VALUES (?, ?, ?)""",
                        (rule_dict["id"], value, triggered[-1]["message"]),
                    )
                    conn.execute(
                        "UPDATE alert_rules SET last_triggered = CURRENT_TIMESTAMP WHERE id = ?",
                        (rule_dict["id"],),
                    )
                    conn.commit()
                    logger.warning(f"[MonitoringStore] ALERT: {triggered[-1]['message']}")
        return triggered

    async def _evaluate_rule(self, conn, rule: dict) -> Optional[float]:
        """Evaluate a single alert rule against recent metrics."""
        metric = rule["metric"]
        comparator = rule["comparator"]
        threshold = rule["threshold"]
        window = rule.get("window_minutes", 60)

        metric_map = {
            "hallucination_rate": "hallucination_detected",
            "escalation_rate": "escalation_signal",
            "avg_quality_score": "quality_score",
            "avg_cost": "cost_usd",
            "total_calls": "run_id",
            "negative_sentiment_rate": "sentiment_arc",
        }

        if metric not in metric_map:
            return None

        col = metric_map[metric]

        if metric == "total_calls":
            row = conn.execute(
                "SELECT COUNT(*) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
                (f"-{window} minutes",),
            ).fetchone()
        elif metric == "hallucination_rate":
            row = conn.execute(
                "SELECT AVG(hallucination_detected) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
                (f"-{window} minutes",),
            ).fetchone()
        elif metric == "escalation_rate":
            row = conn.execute(
                "SELECT AVG(escalation_signal) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
                (f"-{window} minutes",),
            ).fetchone()
        elif metric == "avg_quality_score":
            row = conn.execute(
                "SELECT AVG(quality_score) as val FROM call_metrics WHERE created_at >= datetime('now', ?) AND quality_score IS NOT NULL",
                (f"-{window} minutes",),
            ).fetchone()
        elif metric == "avg_cost":
            row = conn.execute(
                "SELECT AVG(cost_usd) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
                (f"-{window} minutes",),
            ).fetchone()
        elif metric == "negative_sentiment_rate":
            row = conn.execute(
                "SELECT AVG(CASE WHEN sentiment_arc LIKE '%negative%' OR sentiment_arc LIKE '%angry%' OR sentiment_arc LIKE '%frustrated%' THEN 1.0 ELSE 0.0 END) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
                (f"-{window} minutes",),
            ).fetchone()
        else:
            return None

        if row is None or row[0] is None:
            return None

        val = float(row[0])
        fired = False
        if comparator == "gt" and val > threshold:
            fired = True
        elif comparator == "lt" and val < threshold:
            fired = True
        elif comparator == "gte" and val >= threshold:
            fired = True
        elif comparator == "lte" and val <= threshold:
            fired = True
        elif comparator == "eq" and val == threshold:
            fired = True

        return val if fired else None

    async def get_metrics_summary(self, window_minutes: int = 60) -> dict:
        """Get aggregated metrics for the dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT
                    COUNT(*) as total_calls,
                    AVG(quality_score) as avg_quality,
                    AVG(cost_usd) as avg_cost,
                    SUM(cost_usd) as total_cost,
                    AVG(hallucination_detected) as hallucination_rate,
                    AVG(escalation_signal) as escalation_rate,
                    AVG(duration_seconds) as avg_duration,
                    AVG(word_count) as avg_word_count
                FROM call_metrics
                WHERE created_at >= datetime('now', ?)""",
                (f"-{window_minutes} minutes",),
            ).fetchone()

            by_outcome = conn.execute(
                """SELECT outcome, COUNT(*) as count
                   FROM call_metrics
                   WHERE created_at >= datetime('now', ?) AND outcome IS NOT NULL
                   GROUP BY outcome""",
                (f"-{window_minutes} minutes",),
            ).fetchall()

            by_platform = conn.execute(
                """SELECT platform, COUNT(*) as count, AVG(quality_score) as avg_quality
                   FROM call_metrics
                   WHERE created_at >= datetime('now', ?)
                   GROUP BY platform""",
                (f"-{window_minutes} minutes",),
            ).fetchall()

        return {
            "window_minutes": window_minutes,
            "total_calls": row["total_calls"] if row else 0,
            "avg_quality_score": round(row["avg_quality"], 2) if row and row["avg_quality"] else None,
            "avg_cost_usd": round(row["avg_cost"], 6) if row and row["avg_cost"] else None,
            "total_cost_usd": round(row["total_cost"], 6) if row and row["total_cost"] else 0.0,
            "hallucination_rate": round(row["hallucination_rate"], 4) if row and row["hallucination_rate"] else 0.0,
            "escalation_rate": round(row["escalation_rate"], 4) if row and row["escalation_rate"] else 0.0,
            "avg_duration_seconds": round(row["avg_duration"], 1) if row and row["avg_duration"] else None,
            "by_outcome": {r["outcome"]: r["count"] for r in by_outcome} if by_outcome else {},
            "by_platform": {
                r["platform"]: {"count": r["count"], "avg_quality": round(r["avg_quality"], 2) if r["avg_quality"] else None}
                for r in by_platform
            } if by_platform else {},
        }

    # --- Alert Rules CRUD ---

    async def create_rule(
        self,
        name: str,
        metric: str,
        comparator: str,
        threshold: float,
        window_minutes: int = 60,
        notify_url: Optional[str] = None,
        notify_email: Optional[str] = None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO alert_rules (name, metric, comparator, threshold, window_minutes, notify_url, notify_email)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, metric, comparator, threshold, window_minutes, notify_url, notify_email),
            )
            conn.commit()
            rule_id = cursor.lastrowid
        logger.info(f"[MonitoringStore] created alert rule id={rule_id} name={name}")
        return rule_id

    async def list_rules(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM alert_rules ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    async def delete_rule(self, rule_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def list_incidents(self, limit: int = 50) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT i.*, r.name as rule_name, r.metric
                   FROM alert_incidents i
                   JOIN alert_rules r ON i.rule_id = r.id
                   ORDER BY i.triggered_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
