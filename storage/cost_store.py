import os
from pathlib import Path
from utils.logger import logger
from storage.db import get_pool


class CostStore:
    def __init__(self):
        self._pg_pool = None

    async def _get_pool(self):
        if self._pg_pool is None:
            self._pg_pool = await get_pool()
        return self._pg_pool

    async def log_cost(
        self,
        run_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ):
        pool = await self._get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO cost_logs (run_id, provider, model, input_tokens, output_tokens, cost_usd) VALUES ($1, $2, $3, $4, $5, $6)",
                    run_id, provider, model, input_tokens, output_tokens, cost_usd,
                )
        else:
            await self._log_cost_sqlite(run_id, provider, model, input_tokens, output_tokens, cost_usd)
        logger.info(f"[CostStore] logged cost={cost_usd:.6f} provider={provider} model={model}")

    async def get_summary(self) -> dict:
        pool = await self._get_pool()
        if pool:
            return await self._get_summary_pg(pool)
        return await self._get_summary_sqlite()

    async def _get_summary_pg(self, pool) -> dict:
        async with pool.acquire() as conn:
            overall = await conn.fetchrow(
                "SELECT COALESCE(SUM(cost_usd), 0) as total_cost, COALESCE(SUM(input_tokens), 0) as total_input, COALESCE(SUM(output_tokens), 0) as total_output, COUNT(*) as total_calls FROM cost_logs"
            )

            provider_rows = await conn.fetch(
                "SELECT provider, SUM(cost_usd) as cost, COUNT(*) as calls, COALESCE(SUM(input_tokens), 0) as input_tokens, COALESCE(SUM(output_tokens), 0) as output_tokens FROM cost_logs GROUP BY provider"
            )
            by_provider = {
                r["provider"]: {"cost": r["cost"], "calls": r["calls"], "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]}
                for r in provider_rows
            }

            model_rows = await conn.fetch(
                "SELECT model, SUM(cost_usd) as cost, COUNT(*) as calls FROM cost_logs GROUP BY model"
            )
            by_model = {r["model"]: {"cost": r["cost"], "calls": r["calls"]} for r in model_rows}

        return {
            "overall": dict(overall) if overall else {"total_cost": 0, "total_input": 0, "total_output": 0, "total_calls": 0},
            "by_provider": by_provider,
            "by_model": by_model,
        }

    # ── SQLite fallback ───────────────────────────────────────────

    async def _log_cost_sqlite(self, run_id, provider, model, input_tokens, output_tokens, cost_usd):
        import sqlite3
        data_dir = os.environ.get("DATA_DIR", ".")
        db_path = os.getenv("COST_DB_PATH", str(Path(data_dir) / "costs.db"))
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO cost_logs (run_id, provider, model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, provider, model, input_tokens, output_tokens, cost_usd),
            )
            conn.commit()

    async def _get_summary_sqlite(self) -> dict:
        import sqlite3
        data_dir = os.environ.get("DATA_DIR", ".")
        db_path = os.getenv("COST_DB_PATH", str(Path(data_dir) / "costs.db"))
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT SUM(cost_usd) as total_cost, SUM(input_tokens) as total_input, SUM(output_tokens) as total_output, COUNT(*) as total_calls FROM cost_logs"
            )
            overall = dict(cursor.fetchone())

            cursor.execute(
                "SELECT provider, SUM(cost_usd) as cost, COUNT(*) as calls, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens FROM cost_logs GROUP BY provider"
            )
            by_provider = {
                row["provider"]: {"cost": row["cost"], "calls": row["calls"], "input_tokens": row["input_tokens"] or 0, "output_tokens": row["output_tokens"] or 0}
                for row in cursor.fetchall()
            }

            cursor.execute(
                "SELECT model, SUM(cost_usd) as cost, COUNT(*) as calls FROM cost_logs GROUP BY model"
            )
            by_model = {row["model"]: {"cost": row["cost"], "calls": row["calls"]} for row in cursor.fetchall()}

        return {"overall": overall, "by_provider": by_provider, "by_model": by_model}
