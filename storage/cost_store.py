import sqlite3
import os
from utils.logger import logger


class CostStore:
    def __init__(self):
        self.db_path = os.getenv("COST_DB_PATH", "./costs.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"[CostStore] initialized db={self.db_path}")

    async def log_cost(
        self,
        run_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO cost_logs (run_id, provider, model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, provider, model, input_tokens, output_tokens, cost_usd),
            )
            conn.commit()
        logger.info(f"[CostStore] logged cost={cost_usd:.6f} provider={provider} model={model}")

    async def get_summary(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
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
            by_model = {
                row["model"]: {"cost": row["cost"], "calls": row["calls"]}
                for row in cursor.fetchall()
            }

        return {
            "overall": overall,
            "by_provider": by_provider,
            "by_model": by_model,
        }
