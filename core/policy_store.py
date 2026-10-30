"""Explicit company policy rules. Bundled sample policies never activate real checks."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from core.reliability import PolicyRule


class PolicyStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv('POLICY_DB_PATH') or str(
            Path(os.getenv('DATA_DIR', '.')) / 'policies.db'
        )
        self._memory = sqlite3.connect(':memory:') if self.db_path == ':memory:' else None
        if not self._memory:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS policy_rules (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                version TEXT NOT NULL
            )''')

    @contextmanager
    def _connect(self):
        conn = self._memory or sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            if conn is not self._memory:
                conn.close()

    async def list_rules(self) -> list[PolicyRule]:
        with self._connect() as conn:
            rows = conn.execute('SELECT id, title, kind, text, enabled, version FROM policy_rules ORDER BY id').fetchall()
        return [PolicyRule(**{**dict(row), 'enabled': bool(row['enabled'])}) for row in rows]

    async def upsert_rule(self, rule: PolicyRule) -> PolicyRule:
        with self._connect() as conn:
            conn.execute('''INSERT INTO policy_rules (id, title, kind, text, enabled, version)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, kind=excluded.kind,
                    text=excluded.text, enabled=excluded.enabled, version=excluded.version''',
                (rule.id, rule.title, rule.kind, rule.text, int(rule.enabled), rule.version),
            )
        return rule

    async def delete_rule(self, rule_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute('DELETE FROM policy_rules WHERE id = ?', (rule_id,))
            return cursor.rowcount > 0

    def close(self):
        if self._memory is not None:
            self._memory.close()
            self._memory = None
