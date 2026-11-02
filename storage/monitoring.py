import json
import os
from contextlib import closing
from pathlib import Path
from typing import Literal, Optional

from storage.db import get_pool
from utils.logger import logger


def reliability_summary(evaluation) -> dict | None:
    """Return only assessed finding counts; legacy rows have no invented verdict."""
    from pydantic import ValidationError
    from core.reliability import ReliabilityReport

    if isinstance(evaluation, str):
        try:
            evaluation = json.loads(evaluation)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("reliability"), dict):
        return None
    try:
        report = ReliabilityReport.model_validate(evaluation["reliability"])
    except ValidationError:
        return None
    return {
        "status": report.status,
        "checked_rule_count": len(report.checked_rule_ids),
        "finding_count": len(report.findings),
        "confirmed_policy_count": sum(f.category == "policy_violation" and f.status == "confirmed" for f in report.findings),
        "review_count": sum(f.status == "needs_review" for f in report.findings),
        "unverified_claim_count": sum(f.category == "unverified_claim" for f in report.findings),
    }


AssessmentFilter = Literal['policy_matches', 'no_matches', 'not_assessed', 'needs_review', 'insufficient_evidence']


def assessment_kind(summary: dict | None) -> AssessmentFilter:
    """Classify the validated policy summary independently of processing state."""
    if summary is None:
        return 'not_assessed'
    if summary['confirmed_policy_count'] > 0:
        return 'policy_matches'
    if summary['review_count'] > 0 or summary['unverified_claim_count'] > 0:
        return 'needs_review'
    if summary['status'] != 'assessed' or summary['checked_rule_count'] == 0:
        return 'insufficient_evidence'
    return 'no_matches'


class MonitoringStore:
    """Monitoring & alerting store. Tracks metrics and fires threshold-based alerts."""

    async def _get_pool(self):
        return await get_pool()

    async def _runs_columns(self, conn) -> set:
        """Column names actually present in the `runs` table (cached).

        Lets writes work against older databases that predate newer columns
        without requiring a migration.
        """
        cached = self.__dict__.get("_runs_cols")
        if cached is None:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name='runs'"
            )
            cached = {r["column_name"] for r in rows}
            self.__dict__["_runs_cols"] = cached
        return cached

    # ── Runs CRUD ─────────────────────────────────────────────────

    async def log_run(self, result: dict, harness_result=None):
        report = result.get("report", {})
        analysis = result.get("analysis", {})
        provider_data = result.get("provider", {})
        transcript_meta = result.get("transcript_meta", {})

        quality_score = report.get("quality_score") if report and isinstance(report, dict) else None

        truth_score = confidence = None
        if harness_result:
            if isinstance(harness_result, dict):
                truth_score = harness_result.get("truth_score")
                confidence = harness_result.get("confidence")
            else:
                truth_score = harness_result.truth_score
                confidence = harness_result.confidence

        raw = result.get("raw_transcript")
        transcript_preview = raw if raw else None
        if transcript_preview and len(transcript_preview) > 500:
            transcript_preview = transcript_preview[:500] + "…"

        status = result.get("status", "completed")
        if result.get("errors"):
            status = "partial"
        if result.get("status") == "failed":
            status = "failed"

        layer_scores_json = None
        if harness_result:
            ls = harness_result.get("layer_scores") if isinstance(harness_result, dict) else getattr(harness_result, "layer_scores", None)
            if ls:
                layer_scores_json = json.dumps(ls)

        transcript_speakers_json = None
        speakers = result.get("transcript_speakers")
        if speakers:
            transcript_speakers_json = json.dumps(speakers)

        hallucination_evidence = analysis.get("hallucination_evidence") if analysis else None
        policy_evidence = analysis.get("policy_evidence") if analysis else None

        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                # (column, value, cast) — only columns present in the table are written,
                # so old databases without newer columns still accept the row.
                desired = [
                    ("run_id", result.get("run_id", ""), None),
                    ("intent", analysis.get("intent") if analysis else None, None),
                    ("sentiment", analysis.get("sentiment_arc") if analysis else None, None),
                    ("outcome", analysis.get("outcome") if analysis else None, None),
                    ("hallucination_detected", 1 if analysis and analysis.get("hallucination_detected") else 0, None),
                    ("escalation_signal", 1 if analysis and analysis.get("escalation_signal") else 0, None),
                    ("truth_score", truth_score, None),
                    ("confidence", confidence, None),
                    ("quality_score", quality_score, None),
                    ("cost_usd", provider_data.get("cost_usd", 0.0) if provider_data else 0.0, None),
                    ("provider", provider_data.get("name") if provider_data else None, None),
                    ("model", provider_data.get("model") if provider_data else None, None),
                    ("duration_seconds", transcript_meta.get("duration_seconds"), None),
                    ("word_count", transcript_meta.get("word_count"), None),
                    ("transcript_preview", transcript_preview, None),
                    ("transcript_speakers", transcript_speakers_json, "jsonb"),
                    ("layer_scores", layer_scores_json, "jsonb"),
                    ("hallucination_evidence", hallucination_evidence, None),
                    ("policy_evidence", policy_evidence, None),
                    ("status", status, None),
                    ("evaluation", json.dumps(result), "jsonb"),
                ]
                existing = await self._runs_columns(conn)
                use = [(c, v, cast) for c, v, cast in desired if c in existing]
                if not any(c == "run_id" for c, _, _ in use):
                    raise ValueError("runs table has no run_id column — cannot log run")
                cols_sql = ", ".join(c for c, _, _ in use)
                vals_sql = ", ".join(
                    f"${i + 1}{'::' + cast if cast else ''}" for i, (_, _, cast) in enumerate(use)
                )
                update_sql = ", ".join(f"{c}=EXCLUDED.{c}" for c, _, _ in use if c != "run_id")
                await conn.execute(
                    f"INSERT INTO runs ({cols_sql}) VALUES ({vals_sql})"
                    f" ON CONFLICT (run_id) DO UPDATE SET {update_sql}",
                    *(v for _, v, _ in use),
                )
        else:
            await self._log_run_sqlite(result, analysis, provider_data, transcript_meta,
                                       truth_score, confidence, quality_score, status,
                                       layer_scores_json, transcript_speakers_json, transcript_preview,
                                       hallucination_evidence, policy_evidence)
        logger.debug(f"[MonitoringStore] logged run run_id={result.get('run_id')}")

    async def delete_run(self, run_id: str) -> bool:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                result = await conn.execute("DELETE FROM runs WHERE run_id = $1", run_id)
                return bool(result.endswith("1"))
        return await self._delete_run_sqlite(run_id)

    async def get_runs(self, limit: int = 50, offset: int = 0, search: Optional[str] = None,
                       status: Optional[str] = None, assessment: Optional[AssessmentFilter] = None) -> dict:
        pool = await self._get_pool()
        async def page(size: int, start: int) -> dict:
            if pool:
                return await self._get_runs_pg(pool, size, start, search, status)
            return await self._get_runs_sqlite(size, start, search, status)
        if assessment is None:
            return await page(limit, offset)
        # Reuse validated summaries on both databases. Filter before pagination,
        # scanning bounded batches so the result count covers the full search.
        matches, total, start = [], 0, 0
        while True:
            batch = await page(200, start)
            for run in batch['runs']:
                if assessment_kind(run['reliability_summary']) == assessment:
                    if offset <= total < offset + limit:
                        matches.append(run)
                    total += 1
            if len(batch['runs']) < 200:
                break
            start += 200
        return {'runs': matches, 'total': total, 'limit': limit, 'offset': offset}

    async def get_run_summary(self) -> dict:
        """All-time persisted runs. Demo IDs are reserved by the legacy seeder."""
        query = """SELECT COUNT(*) AS total_calls,
            COALESCE(SUM(CASE WHEN run_id LIKE 'demo-%' THEN 1 ELSE 0 END), 0) AS demo_calls,
            COALESCE(SUM(CASE WHEN run_id NOT LIKE 'demo-%' THEN 1 ELSE 0 END), 0) AS real_calls,
            COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) AS completed_calls,
            COALESCE(SUM(CASE WHEN run_id NOT LIKE 'demo-%' AND status = 'completed'
                AND hallucination_detected = 1 THEN 1 ELSE 0 END), 0) AS flagged_calls,
            COALESCE(SUM(CASE WHEN run_id NOT LIKE 'demo-%' AND status = 'completed'
                AND escalation_signal = 1 THEN 1 ELSE 0 END), 0) AS escalated_calls,
            COALESCE(SUM(CASE WHEN run_id NOT LIKE 'demo-%' AND status = 'completed'
                THEN 1 ELSE 0 END), 0) AS evaluated_real_calls
            FROM runs"""
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query)
                evaluations = await conn.fetch("SELECT run_id, evaluation FROM runs")
        else:
            with self._sqlite_conn() as conn:
                row = conn.execute(query).fetchone()
                evaluations = conn.execute("SELECT run_id, evaluation FROM runs").fetchall()
        result = dict(row)
        denominator = result["evaluated_real_calls"]
        result["hallucination_rate"] = result["flagged_calls"] / denominator if denominator else None
        result["escalation_rate"] = result["escalated_calls"] / denominator if denominator else None
        result["scope"] = "all_time_persisted_runs"
        result.update(confirmed_policy_calls=0, review_calls=0, evaluated_policy_calls=0, legacy_calls=0)
        for evaluation in evaluations:
            if evaluation["run_id"].startswith("demo-"):
                continue
            summary = reliability_summary(evaluation["evaluation"])
            if summary is None:
                result["legacy_calls"] += 1
                continue
            result["confirmed_policy_calls"] += int(summary["confirmed_policy_count"] > 0)
            result["review_calls"] += int(summary["review_count"] > 0 or summary["status"] == "insufficient_evidence")
            result["evaluated_policy_calls"] += int(summary["status"] == "assessed")
        return result

    async def get_run(self, run_id: str) -> Optional[dict]:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
            if not row:
                return None
            d = dict(row)
            for json_field in ("layer_scores", "transcript_speakers", "evaluation"):
                if d.get(json_field) and isinstance(d[json_field], str):
                    try:
                        d[json_field] = json.loads(d[json_field])
                    except (json.JSONDecodeError, TypeError):
                        d[json_field] = None
            return d
        return await self._get_run_sqlite(run_id)

    async def log_call(self, result: dict):
        report = result.get("report", {})
        analysis = result.get("analysis", {})
        provider_data = result.get("provider", {})
        quality_score = report.get("quality_score") if report and isinstance(report, dict) else None

        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO call_metrics (run_id, platform, intent, sentiment_arc, outcome,
                       hallucination_detected, escalation_signal, quality_score, cost_usd,
                       duration_seconds, word_count, provider, model)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                    result.get("run_id", ""), result.get("platform", "direct"),
                    analysis.get("intent") if analysis else None,
                    analysis.get("sentiment_arc") if analysis else None,
                    analysis.get("outcome") if analysis else None,
                    1 if analysis and analysis.get("hallucination_detected") else 0,
                    1 if analysis and analysis.get("escalation_signal") else 0,
                    quality_score, provider_data.get("cost_usd", 0.0) if provider_data else 0.0,
                    result.get("transcript_meta", {}).get("duration_seconds"),
                    result.get("transcript_meta", {}).get("word_count"),
                    provider_data.get("name") if provider_data else None,
                    provider_data.get("model") if provider_data else None,
                )
        else:
            await self._log_call_sqlite(result, analysis, provider_data, quality_score)
        logger.debug(f"[MonitoringStore] logged run_id={result.get('run_id')}")

    # ── Alerts ────────────────────────────────────────────────────

    async def check_alerts(self) -> list[dict]:
        triggered = []
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                rules = await conn.fetch("SELECT * FROM alert_rules WHERE enabled = 1")
                for rule in rules:
                    rule_dict = dict(rule)
                    value = await self._evaluate_rule_pg(conn, rule_dict)
                    if value is not None:
                        msg = f"{rule_dict['name']}: {rule_dict['metric']}={value} (threshold={rule_dict['threshold']})"
                        triggered.append({"rule_id": rule_dict["id"], "rule_name": rule_dict["name"], "metric": rule_dict["metric"], "threshold": rule_dict["threshold"], "actual_value": value, "message": msg})
                        await conn.execute("INSERT INTO alert_incidents (rule_id, metric_value, message) VALUES ($1, $2, $3)", rule_dict["id"], value, msg)
                        await conn.execute("UPDATE alert_rules SET last_triggered = NOW() WHERE id = $1", rule_dict["id"])
                        logger.warning(f"[MonitoringStore] ALERT: {msg}")
        else:
            triggered = await self._check_alerts_sqlite()
        return triggered

    async def get_metrics_summary(self, window_minutes: int = 60) -> dict:
        pool = await self._get_pool()
        if pool:
            return await self._get_metrics_pg(pool, window_minutes)
        return await self._get_metrics_sqlite(window_minutes)

    async def get_truth_history(self, limit: int = 12) -> list[float]:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT truth_score FROM runs WHERE truth_score IS NOT NULL ORDER BY created_at DESC LIMIT $1", limit
                )
            return [r["truth_score"] for r in reversed(rows)]
        return await self._get_truth_history_sqlite(limit)

    # ── Alert Rules CRUD ──────────────────────────────────────────

    async def create_rule(self, name, metric, comparator, threshold, window_minutes=60, notify_url=None, notify_email=None) -> int:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO alert_rules (name, metric, comparator, threshold, window_minutes, notify_url, notify_email) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
                    name, metric, comparator, threshold, window_minutes, notify_url, notify_email,
                )
                return int(row["id"])
        return await self._create_rule_sqlite(name, metric, comparator, threshold, window_minutes, notify_url, notify_email)

    async def list_rules(self) -> list[dict]:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM alert_rules ORDER BY created_at DESC")
                return [dict(r) for r in rows]
        return await self._list_rules_sqlite()

    async def delete_rule(self, rule_id: int) -> bool:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                result = await conn.execute("DELETE FROM alert_rules WHERE id = $1", rule_id)
                return bool(result.endswith("1"))
        return await self._delete_rule_sqlite(rule_id)

    async def list_incidents(self, limit: int = 50) -> list[dict]:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT i.*, r.name as rule_name, r.metric
                       FROM alert_incidents i LEFT JOIN alert_rules r ON i.rule_id = r.id
                       ORDER BY i.triggered_at DESC LIMIT $1""", limit
                )
                return [dict(r) for r in rows]
        return await self._list_incidents_sqlite(limit)

    async def create_run_incident(self, run_id: str, kind: str, message: str) -> None:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO alert_incidents (rule_id, metric_value, message) VALUES (NULL, $1, $2)", kind, message)
        else:
            await self._create_run_incident_sqlite(run_id, kind, message)
        logger.warning(f"[MonitoringStore] INCIDENT: {message} (run={run_id})")

    # ── PG alert evaluation ───────────────────────────────────────

    async def _evaluate_rule_pg(self, conn, rule: dict) -> Optional[float]:
        metric = rule["metric"]
        comparator = rule["comparator"]
        threshold = rule["threshold"]
        window = int(rule.get("window_minutes", 60))

        queries = {
            "hallucination_rate": "SELECT AVG(hallucination_detected) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval",
            "escalation_rate": "SELECT AVG(escalation_signal) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval",
            "avg_quality_score": "SELECT AVG(quality_score) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval AND quality_score IS NOT NULL",
            "avg_cost": "SELECT AVG(cost_usd) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval",
            "total_calls": "SELECT COUNT(*) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval",
            "negative_sentiment_rate": "SELECT AVG(CASE WHEN sentiment_arc LIKE '%negative%' OR sentiment_arc LIKE '%angry%' OR sentiment_arc LIKE '%frustrated%' THEN 1.0 ELSE 0.0 END) as val FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval",
        }

        if metric not in queries:
            return None

        row = await conn.fetchrow(queries[metric], str(window))
        if not row or row[0] is None:
            return None

        val = float(row[0])
        ops = {"gt": val > threshold, "lt": val < threshold, "gte": val >= threshold, "lte": val <= threshold, "eq": val == threshold}
        return val if ops.get(comparator, False) else None

    async def _get_runs_pg(self, pool, limit, offset, search, status) -> dict:
        where = []
        params = []
        idx = 1
        if search:
            where.append(f"(run_id LIKE '%' || ${idx} || '%' OR intent LIKE '%' || ${idx} || '%')")
            params.append(search)
            idx += 1
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        async with pool.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM runs {where_sql}", *params)
            rows = await conn.fetch(
                f"SELECT run_id, intent, sentiment, outcome, hallucination_detected, escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model, duration_seconds, word_count, transcript_preview, layer_scores, status, created_at, evaluation FROM runs {where_sql} ORDER BY created_at DESC, run_id DESC LIMIT ${idx} OFFSET ${idx+1}",
                *params, limit, offset
            )

        runs = []
        for r in rows:
            d = dict(r)
            if d.get("transcript_preview"):
                d["transcript_preview"] = d["transcript_preview"][:200] + ("…" if len(d["transcript_preview"]) > 200 else "")
            if d.get("layer_scores") and isinstance(d["layer_scores"], str):
                try:
                    d["layer_scores"] = json.loads(d["layer_scores"])
                except (json.JSONDecodeError, TypeError):
                    d["layer_scores"] = None
            d["reliability_summary"] = reliability_summary(d.pop("evaluation", None))
            runs.append(d)

        return {"runs": runs, "total": total, "limit": limit, "offset": offset}

    async def _get_metrics_pg(self, pool, window_minutes) -> dict:
        window = int(window_minutes)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT COUNT(*) as total_calls, AVG(quality_score) as avg_quality, AVG(cost_usd) as avg_cost,
                    SUM(cost_usd) as total_cost, AVG(hallucination_detected) as hallucination_rate,
                    AVG(escalation_signal) as escalation_rate, AVG(duration_seconds) as avg_duration,
                    AVG(word_count) as avg_word_count
                FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval""",
                str(window),
            )
            by_outcome = await conn.fetch(
                "SELECT outcome, COUNT(*) as count FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval AND outcome IS NOT NULL GROUP BY outcome",
                str(window),
            )
            by_platform = await conn.fetch(
                "SELECT platform, COUNT(*) as count, AVG(quality_score) as avg_quality FROM call_metrics WHERE created_at >= NOW() - ($1 || ' minutes')::interval GROUP BY platform",
                str(window),
            )

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
            "by_platform": {r["platform"]: {"count": r["count"], "avg_quality": round(r["avg_quality"], 2) if r["avg_quality"] else None} for r in by_platform} if by_platform else {},
        }

    # ── SQLite fallback (all methods) ─────────────────────────────

    def _sqlite_conn(self):
        import sqlite3
        data_dir = os.environ.get("DATA_DIR", ".")
        db_path = os.getenv("MONITORING_DB_PATH", str(Path(data_dir) / "monitoring.db"))
        Path(db_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                intent TEXT, sentiment TEXT, outcome TEXT,
                hallucination_detected INTEGER DEFAULT 0,
                escalation_signal INTEGER DEFAULT 0,
                truth_score REAL, confidence TEXT, quality_score REAL,
                cost_usd REAL DEFAULT 0.0, provider TEXT, model TEXT,
                duration_seconds REAL, word_count INTEGER,
                transcript_preview TEXT, transcript_speakers TEXT,
                layer_scores TEXT, status TEXT DEFAULT 'completed',
                hallucination_evidence TEXT, policy_evidence TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS call_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                platform TEXT, intent TEXT, sentiment_arc TEXT, outcome TEXT,
                hallucination_detected INTEGER DEFAULT 0,
                escalation_signal INTEGER DEFAULT 0,
                quality_score REAL, cost_usd REAL DEFAULT 0.0,
                duration_seconds REAL, word_count INTEGER,
                provider TEXT, model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, metric TEXT NOT NULL,
                comparator TEXT NOT NULL, threshold REAL NOT NULL,
                window_minutes INTEGER DEFAULT 60, enabled INTEGER DEFAULT 1,
                notify_url TEXT, notify_email TEXT,
                last_triggered TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER, metric_value REAL, message TEXT,
                status TEXT DEFAULT 'active',
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        if "evaluation" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN evaluation TEXT")
        conn.commit()
        return closing(conn)

    async def _log_run_sqlite(self, result, analysis, provider_data, transcript_meta, truth_score, confidence, quality_score, status, layer_scores_json, transcript_speakers_json, transcript_preview, hallucination_evidence, policy_evidence):
        with self._sqlite_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs (run_id, intent, sentiment, outcome, hallucination_detected,
                   escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model,
                   duration_seconds, word_count, transcript_preview, transcript_speakers, layer_scores,
                   hallucination_evidence, policy_evidence, status, evaluation)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (result.get("run_id", ""), analysis.get("intent") if analysis else None, analysis.get("sentiment_arc") if analysis else None,
                 analysis.get("outcome") if analysis else None, 1 if analysis and analysis.get("hallucination_detected") else 0,
                 1 if analysis and analysis.get("escalation_signal") else 0, truth_score, confidence, quality_score,
                 provider_data.get("cost_usd", 0.0) if provider_data else 0.0, provider_data.get("name") if provider_data else None,
                 provider_data.get("model") if provider_data else None, transcript_meta.get("duration_seconds"),
                 transcript_meta.get("word_count"), transcript_preview, transcript_speakers_json, layer_scores_json,
                 hallucination_evidence, policy_evidence, status, json.dumps(result)),
            )
            conn.commit()

    async def _delete_run_sqlite(self, run_id) -> bool:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return bool(cursor.rowcount > 0)

    async def _get_runs_sqlite(self, limit, offset, search, status) -> dict:
        with self._sqlite_conn() as conn:
            where, params = [], []
            if search:
                where.append("(run_id LIKE ? OR intent LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            if status:
                where.append("status = ?")
                params.append(status)
            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            total = conn.execute(f"SELECT COUNT(*) as cnt FROM runs {where_sql}", params).fetchone()["cnt"]
            rows = conn.execute(f"SELECT run_id, intent, sentiment, outcome, hallucination_detected, escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model, duration_seconds, word_count, transcript_preview, layer_scores, status, created_at, evaluation FROM runs {where_sql} ORDER BY created_at DESC, run_id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        runs = []
        for r in rows:
            d = dict(r)
            if d.get("transcript_preview"):
                d["transcript_preview"] = d["transcript_preview"][:200] + ("…" if len(d["transcript_preview"]) > 200 else "")
            if d.get("layer_scores"):
                try:
                    d["layer_scores"] = json.loads(d["layer_scores"])
                except (json.JSONDecodeError, TypeError):
                    d["layer_scores"] = None
            d["reliability_summary"] = reliability_summary(d.pop("evaluation", None))
            runs.append(d)
        return {"runs": runs, "total": total, "limit": limit, "offset": offset}

    async def _get_run_sqlite(self, run_id) -> Optional[dict]:
        with self._sqlite_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for f in ("layer_scores", "transcript_speakers", "evaluation"):
            if d.get(f):
                try:
                    d[f] = json.loads(d[f])
                except (json.JSONDecodeError, TypeError):
                    d[f] = None
        return d

    async def _log_call_sqlite(self, result, analysis, provider_data, quality_score):
        with self._sqlite_conn() as conn:
            conn.execute("INSERT INTO call_metrics (run_id, platform, intent, sentiment_arc, outcome, hallucination_detected, escalation_signal, quality_score, cost_usd, duration_seconds, word_count, provider, model) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (result.get("run_id", ""), result.get("platform", "direct"), analysis.get("intent") if analysis else None, analysis.get("sentiment_arc") if analysis else None,
                 analysis.get("outcome") if analysis else None, 1 if analysis and analysis.get("hallucination_detected") else 0,
                 1 if analysis and analysis.get("escalation_signal") else 0, quality_score, provider_data.get("cost_usd", 0.0) if provider_data else 0.0,
                 result.get("transcript_meta", {}).get("duration_seconds"), result.get("transcript_meta", {}).get("word_count"),
                 provider_data.get("name") if provider_data else None, provider_data.get("model") if provider_data else None))
            conn.commit()

    async def _check_alerts_sqlite(self) -> list[dict]:
        triggered = []
        with self._sqlite_conn() as conn:
            rules = conn.execute("SELECT * FROM alert_rules WHERE enabled = 1").fetchall()
            for rule in rules:
                rule_dict = dict(rule)
                value = await self._evaluate_rule_sqlite(conn, rule_dict)
                if value is not None:
                    msg = f"{rule_dict['name']}: {rule_dict['metric']}={value} (threshold={rule_dict['threshold']})"
                    triggered.append({"rule_id": rule_dict["id"], "rule_name": rule_dict["name"], "metric": rule_dict["metric"], "threshold": rule_dict["threshold"], "actual_value": value, "message": msg})
                    conn.execute("INSERT INTO alert_incidents (rule_id, metric_value, message) VALUES (?, ?, ?)", (rule_dict["id"], value, msg))
                    conn.execute("UPDATE alert_rules SET last_triggered = CURRENT_TIMESTAMP WHERE id = ?", (rule_dict["id"],))
                    conn.commit()
                    logger.warning(f"[MonitoringStore] ALERT: {msg}")
        return triggered

    async def _evaluate_rule_sqlite(self, conn, rule) -> Optional[float]:
        metric, comparator, threshold = rule["metric"], rule["comparator"], rule["threshold"]
        window = int(rule.get("window_minutes", 60))
        queries = {
            "hallucination_rate": "SELECT AVG(hallucination_detected) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
            "escalation_rate": "SELECT AVG(escalation_signal) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
            "avg_quality_score": "SELECT AVG(quality_score) as val FROM call_metrics WHERE created_at >= datetime('now', ?) AND quality_score IS NOT NULL",
            "avg_cost": "SELECT AVG(cost_usd) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
            "total_calls": "SELECT COUNT(*) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
            "negative_sentiment_rate": "SELECT AVG(CASE WHEN sentiment_arc LIKE '%negative%' OR sentiment_arc LIKE '%angry%' OR sentiment_arc LIKE '%frustrated%' THEN 1.0 ELSE 0.0 END) as val FROM call_metrics WHERE created_at >= datetime('now', ?)",
        }
        if metric not in queries:
            return None
        row = conn.execute(queries[metric], (f"-{window} minutes",)).fetchone()
        if not row or row[0] is None:
            return None
        val = float(row[0])
        ops = {"gt": val > threshold, "lt": val < threshold, "gte": val >= threshold, "lte": val <= threshold, "eq": val == threshold}
        return val if ops.get(comparator, False) else None

    async def _get_metrics_sqlite(self, window_minutes) -> dict:
        window = int(window_minutes)
        time_filter = f"-{window} minutes"
        with self._sqlite_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as total_calls, AVG(quality_score) as avg_quality, AVG(cost_usd) as avg_cost, SUM(cost_usd) as total_cost, AVG(hallucination_detected) as hallucination_rate, AVG(escalation_signal) as escalation_rate, AVG(duration_seconds) as avg_duration, AVG(word_count) as avg_word_count FROM call_metrics WHERE created_at >= datetime('now', ?)", (time_filter,)).fetchone()
            by_outcome = conn.execute("SELECT outcome, COUNT(*) as count FROM call_metrics WHERE created_at >= datetime('now', ?) AND outcome IS NOT NULL GROUP BY outcome", (time_filter,)).fetchall()
            by_platform = conn.execute("SELECT platform, COUNT(*) as count, AVG(quality_score) as avg_quality FROM call_metrics WHERE created_at >= datetime('now', ?) GROUP BY platform", (time_filter,)).fetchall()
        return {
            "window_minutes": window_minutes, "total_calls": row["total_calls"] if row else 0,
            "avg_quality_score": round(row["avg_quality"], 2) if row and row["avg_quality"] else None,
            "avg_cost_usd": round(row["avg_cost"], 6) if row and row["avg_cost"] else None,
            "total_cost_usd": round(row["total_cost"], 6) if row and row["total_cost"] else 0.0,
            "hallucination_rate": round(row["hallucination_rate"], 4) if row and row["hallucination_rate"] else 0.0,
            "escalation_rate": round(row["escalation_rate"], 4) if row and row["escalation_rate"] else 0.0,
            "avg_duration_seconds": round(row["avg_duration"], 1) if row and row["avg_duration"] else None,
            "by_outcome": {r["outcome"]: r["count"] for r in by_outcome} if by_outcome else {},
            "by_platform": {r["platform"]: {"count": r["count"], "avg_quality": round(r["avg_quality"], 2) if r["avg_quality"] else None} for r in by_platform} if by_platform else {},
        }

    async def _get_truth_history_sqlite(self, limit) -> list[float]:
        with self._sqlite_conn() as conn:
            rows = conn.execute("SELECT truth_score FROM runs WHERE truth_score IS NOT NULL ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [float(r[0]) for r in reversed(rows)]

    async def _create_rule_sqlite(self, name, metric, comparator, threshold, window_minutes, notify_url, notify_email) -> int:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("INSERT INTO alert_rules (name, metric, comparator, threshold, window_minutes, notify_url, notify_email) VALUES (?,?,?,?,?,?,?)", (name, metric, comparator, threshold, window_minutes, notify_url, notify_email))
            conn.commit()
            return int(cursor.lastrowid)

    async def _list_rules_sqlite(self) -> list[dict]:
        with self._sqlite_conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM alert_rules ORDER BY created_at DESC").fetchall()]

    async def _delete_rule_sqlite(self, rule_id) -> bool:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return bool(cursor.rowcount > 0)

    async def _list_incidents_sqlite(self, limit) -> list[dict]:
        with self._sqlite_conn() as conn:
            return [dict(r) for r in conn.execute("SELECT i.*, r.name as rule_name, r.metric FROM alert_incidents i LEFT JOIN alert_rules r ON i.rule_id = r.id ORDER BY i.triggered_at DESC LIMIT ?", (limit,)).fetchall()]

    async def _create_run_incident_sqlite(self, run_id, kind, message) -> None:
        with self._sqlite_conn() as conn:
            conn.execute("INSERT INTO alert_incidents (rule_id, metric_value, message) VALUES (NULL, ?, ?)", (kind, message))
            conn.commit()
