"""Completed Bolna event deduplication for a shared private deployment volume."""

import os
import sqlite3
import time
import uuid
from pathlib import Path


class WebhookReceipts:
    def __init__(self):
        directory = Path(os.getenv('DATA_DIR', '/tmp')) / 'webhook_receipts'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / 'receipts.sqlite'
        with self._connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS receipts (call_id TEXT PRIMARY KEY, token TEXT NOT NULL, expires REAL NOT NULL, run_id TEXT)')
        self.path.chmod(0o600)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def claim(self, call_id: str) -> tuple[str, str]:
        now, token = time.time(), str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT token, expires, run_id FROM receipts WHERE call_id=?', (call_id,)).fetchone()
            if row and row[2]:
                return 'completed', row[2]
            if row and row[1] > now:
                return 'processing', ''
            connection.execute('INSERT INTO receipts(call_id,token,expires) VALUES(?,?,?) ON CONFLICT(call_id) DO UPDATE SET token=excluded.token, expires=excluded.expires, run_id=NULL', (call_id, token, now + 600))
        return 'claimed', token

    def complete(self, call_id: str, token: str, run_id: str):
        if not run_id:
            raise ValueError('Persisted run ID required')
        with self._connect() as connection:
            updated = connection.execute('UPDATE receipts SET run_id=? WHERE call_id=? AND token=? AND run_id IS NULL', (run_id, call_id, token)).rowcount
        if updated != 1:
            raise ValueError('Webhook processing lease changed; inspect the saved run before retrying')

    def release(self, call_id: str, token: str):
        with self._connect() as connection:
            connection.execute('DELETE FROM receipts WHERE call_id=? AND token=? AND run_id IS NULL', (call_id, token))
