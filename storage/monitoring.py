import os
import json
from pathlib import Path
from typing import Optional
from utils.logger import logger
from storage.db import get_pool


class MonitoringStore:
    """Monitoring & alerting store. Tracks metrics and fires threshold-based alerts."""

    def __init__(self):
        self._pg_pool = None

    async def _get_pool(self):
        if self._pg_pool is None:
            self._pg_pool = await get_pool()
        return self._pg_pool

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

        status = "completed"
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

        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO runs (run_id, intent, sentiment, outcome, hallucination_detected,
                       escalation_signal, truth_score, confidence, quality_score, cost_usd,
                       provider, model, duration_seconds, word_count, transcript_preview,
                       transcript_speakers, layer_scores, status)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17::jsonb,$18)
                       ON CONFLICT (run_id) DO UPDATE SET
                       intent=EXCLUDED.intent, sentiment=EXCLUDED.sentiment, outcome=EXCLUDED.outcome,
                       hallucination_detected=EXCLUDED.hallucination_detected, escalation_signal=EXCLUDED.escalation_signal,
                       truth_score=EXCLUDED.truth_score, confidence=EXCLUDED.confidence, quality_score=EXCLUDED.quality_score,
                       cost_usd=EXCLUDED.cost_usd, provider=EXCLUDED.provider, model=EXCLUDED.model,
                       duration_seconds=EXCLUDED.duration_seconds, word_count=EXCLUDED.word_count,
                       transcript_preview=EXCLUDED.transcript_preview, transcript_speakers=EXCLUDED.transcript_speakers,
                       layer_scores=EXCLUDED.layer_scores, status=EXCLUDED.status""",
                    result.get("run_id", ""),
                    analysis.get("intent") if analysis else None,
                    analysis.get("sentiment_arc") if analysis else None,
                    analysis.get("outcome") if analysis else None,
                    1 if analysis and analysis.get("hallucination_detected") else 0,
                    1 if analysis and analysis.get("escalation_signal") else 0,
                    truth_score, confidence, quality_score,
                    provider_data.get("cost_usd", 0.0) if provider_data else 0.0,
                    provider_data.get("name") if provider_data else None,
                    provider_data.get("model") if provider_data else None,
                    transcript_meta.get("duration_seconds"),
                    transcript_meta.get("word_count"),
                    transcript_preview, transcript_speakers_json, layer_scores_json, status,
                )
        else:
            await self._log_run_sqlite(result, analysis, provider_data, transcript_meta,
                                       truth_score, confidence, quality_score, status,
                                       layer_scores_json, transcript_speakers_json, transcript_preview)
        logger.debug(f"[MonitoringStore] logged run run_id={result.get('run_id')}")

    async def delete_run(self, run_id: str) -> bool:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                result = await conn.execute("DELETE FROM runs WHERE run_id = $1", run_id)
                return result.endswith("1")
        return await self._delete_run_sqlite(run_id)

    async def get_runs(self, limit: int = 50, offset: int = 0, search: Optional[str] = None, status: Optional[str] = None) -> dict:
        pool = await self._get_pool()
        if pool:
            return await self._get_runs_pg(pool, limit, offset, search, status)
        return await self._get_runs_sqlite(limit, offset, search, status)

    async def get_run(self, run_id: str) -> Optional[dict]:
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
            if not row:
                return None
            d = dict(row)
            for json_field in ("layer_scores", "transcript_speakers"):
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
                return row["id"]
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
                return result.endswith("1")
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
        window = rule.get("window_minutes", 60)

        queries = {
            "hallucination_rate": f"SELECT AVG(hallucination_detected) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes'",
            "escalation_rate": f"SELECT AVG(escalation_signal) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes'",
            "avg_quality_score": f"SELECT AVG(quality_score) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes' AND quality_score IS NOT NULL",
            "avg_cost": f"SELECT AVG(cost_usd) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes'",
            "total_calls": f"SELECT COUNT(*) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes'",
            "negative_sentiment_rate": f"SELECT AVG(CASE WHEN sentiment_arc LIKE '%negative%' OR sentiment_arc LIKE '%angry%' OR sentiment_arc LIKE '%frustrated%' THEN 1.0 ELSE 0.0 END) as val FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window} minutes'",
        }

        if metric not in queries:
            return None

        row = await conn.fetchrow(queries[metric])
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
                f"SELECT run_id, intent, sentiment, outcome, hallucination_detected, escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model, duration_seconds, word_count, transcript_preview, transcript_speakers, layer_scores, status, created_at FROM runs {where_sql} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
                *params, limit, offset
            )

        runs = []
        for r in rows:
            d = dict(r)
            for json_field in ("layer_scores", "transcript_speakers"):
                if d.get(json_field) and isinstance(d[json_field], str):
                    try:
                        d[json_field] = json.loads(d[json_field])
                    except (json.JSONDecodeError, TypeError):
                        d[json_field] = None
            runs.append(d)

        return {"runs": runs, "total": total, "limit": limit, "offset": offset}

    async def _get_metrics_pg(self, pool, window_minutes) -> dict:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT COUNT(*) as total_calls, AVG(quality_score) as avg_quality, AVG(cost_usd) as avg_cost,
                    SUM(cost_usd) as total_cost, AVG(hallucination_detected) as hallucination_rate,
                    AVG(escalation_signal) as escalation_rate, AVG(duration_seconds) as avg_duration,
                    AVG(word_count) as avg_word_count
                FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window_minutes} minutes'"""
            )
            by_outcome = await conn.fetch(
                f"SELECT outcome, COUNT(*) as count FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window_minutes} minutes' AND outcome IS NOT NULL GROUP BY outcome"
            )
            by_platform = await conn.fetch(
                f"SELECT platform, COUNT(*) as count, AVG(quality_score) as avg_quality FROM call_metrics WHERE created_at >= NOW() - INTERVAL '{window_minutes} minutes' GROUP BY platform"
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
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def _log_run_sqlite(self, result, analysis, provider_data, transcript_meta, truth_score, confidence, quality_score, status, layer_scores_json, transcript_speakers_json, transcript_preview):
        import sqlite3
        with self._sqlite_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs (run_id, intent, sentiment, outcome, hallucination_detected,
                   escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model,
                   duration_seconds, word_count, transcript_preview, transcript_speakers, layer_scores, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (result.get("run_id", ""), analysis.get("intent") if analysis else None, analysis.get("sentiment_arc") if analysis else None,
                 analysis.get("outcome") if analysis else None, 1 if analysis and analysis.get("hallucination_detected") else 0,
                 1 if analysis and analysis.get("escalation_signal") else 0, truth_score, confidence, quality_score,
                 provider_data.get("cost_usd", 0.0) if provider_data else 0.0, provider_data.get("name") if provider_data else None,
                 provider_data.get("model") if provider_data else None, transcript_meta.get("duration_seconds"),
                 transcript_meta.get("word_count"), transcript_preview, transcript_speakers_json, layer_scores_json, status),
            )
            conn.commit()

    async def _delete_run_sqlite(self, run_id) -> bool:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount > 0

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
            rows = conn.execute(f"SELECT run_id, intent, sentiment, outcome, hallucination_detected, escalation_signal, truth_score, confidence, quality_score, cost_usd, provider, model, duration_seconds, word_count, transcript_preview, transcript_speakers, layer_scores, status, created_at FROM runs {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        runs = []
        for r in rows:
            d = dict(r)
            for f in ("layer_scores", "transcript_speakers"):
                if d.get(f):
                    try: d[f] = json.loads(d[f])
                    except: d[f] = None
            runs.append(d)
        return {"runs": runs, "total": total, "limit": limit, "offset": offset}

    async def _get_run_sqlite(self, run_id) -> Optional[dict]:
        with self._sqlite_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row: return None
        d = dict(row)
        for f in ("layer_scores", "transcript_speakers"):
            if d.get(f):
                try: d[f] = json.loads(d[f])
                except: d[f] = None
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
        metric, comparator, threshold, window = rule["metric"], rule["comparator"], rule["threshold"], rule.get("window_minutes", 60)
        queries = {
            "hallucination_rate": f"SELECT AVG(hallucination_detected) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes')",
            "escalation_rate": f"SELECT AVG(escalation_signal) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes')",
            "avg_quality_score": f"SELECT AVG(quality_score) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes') AND quality_score IS NOT NULL",
            "avg_cost": f"SELECT AVG(cost_usd) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes')",
            "total_calls": f"SELECT COUNT(*) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes')",
            "negative_sentiment_rate": f"SELECT AVG(CASE WHEN sentiment_arc LIKE '%negative%' OR sentiment_arc LIKE '%angry%' OR sentiment_arc LIKE '%frustrated%' THEN 1.0 ELSE 0.0 END) as val FROM call_metrics WHERE created_at >= datetime('now', '-{window} minutes')",
        }
        if metric not in queries: return None
        row = conn.execute(queries[metric]).fetchone()
        if not row or row[0] is None: return None
        val = float(row[0])
        ops = {"gt": val > threshold, "lt": val < threshold, "gte": val >= threshold, "lte": val <= threshold, "eq": val == threshold}
        return val if ops.get(comparator, False) else None

    async def _get_metrics_sqlite(self, window_minutes) -> dict:
        with self._sqlite_conn() as conn:
            row = conn.execute(f"SELECT COUNT(*) as total_calls, AVG(quality_score) as avg_quality, AVG(cost_usd) as avg_cost, SUM(cost_usd) as total_cost, AVG(hallucination_detected) as hallucination_rate, AVG(escalation_signal) as escalation_rate, AVG(duration_seconds) as avg_duration, AVG(word_count) as avg_word_count FROM call_metrics WHERE created_at >= datetime('now', '-{window_minutes} minutes')").fetchone()
            by_outcome = conn.execute(f"SELECT outcome, COUNT(*) as count FROM call_metrics WHERE created_at >= datetime('now', '-{window_minutes} minutes') AND outcome IS NOT NULL GROUP BY outcome").fetchall()
            by_platform = conn.execute(f"SELECT platform, COUNT(*) as count, AVG(quality_score) as avg_quality FROM call_metrics WHERE created_at >= datetime('now', '-{window_minutes} minutes') GROUP BY platform").fetchall()
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
        return [r[0] for r in reversed(rows)]

    async def _create_rule_sqlite(self, name, metric, comparator, threshold, window_minutes, notify_url, notify_email) -> int:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("INSERT INTO alert_rules (name, metric, comparator, threshold, window_minutes, notify_url, notify_email) VALUES (?,?,?,?,?,?,?)", (name, metric, comparator, threshold, window_minutes, notify_url, notify_email))
            conn.commit()
            return cursor.lastrowid

    async def _list_rules_sqlite(self) -> list[dict]:
        with self._sqlite_conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM alert_rules ORDER BY created_at DESC").fetchall()]

    async def _delete_rule_sqlite(self, rule_id) -> bool:
        with self._sqlite_conn() as conn:
            cursor = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def _list_incidents_sqlite(self, limit) -> list[dict]:
        with self._sqlite_conn() as conn:
            return [dict(r) for r in conn.execute("SELECT i.*, r.name as rule_name, r.metric FROM alert_incidents i LEFT JOIN alert_rules r ON i.rule_id = r.id ORDER BY i.triggered_at DESC LIMIT ?", (limit,)).fetchall()]

    async def _create_run_incident_sqlite(self, run_id, kind, message) -> None:
        with self._sqlite_conn() as conn:
            conn.execute("INSERT INTO alert_incidents (rule_id, metric_value, message) VALUES (NULL, ?, ?)", (kind, message))
            conn.commit()
