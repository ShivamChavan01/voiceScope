"""Private, expiring post-call STT artifacts, scoped to the authenticated API key."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class STTReviewStore:
    def __init__(self, directory: str | Path | None = None):
        root = Path(directory or os.getenv('STT_REVIEW_DIR') or Path(os.getenv('DATA_DIR', '.')) / 'stt_reviews')
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        self.path = root / 'reviews.sqlite'
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self._connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS stt_artifacts (
                owner TEXT NOT NULL, run_id TEXT NOT NULL, expires REAL NOT NULL,
                audio BLOB, content_type TEXT, audio_info TEXT, reference TEXT, review TEXT,
                PRIMARY KEY(owner, run_id))''')
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(stt_artifacts)')}
            if 'annotations' not in columns:
                conn.execute('ALTER TABLE stt_artifacts ADD COLUMN annotations TEXT')
            conn.execute('DELETE FROM stt_artifacts WHERE expires < ?', (time.time(),))

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA secure_delete = ON')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def read(self, owner: str, run_id: str) -> dict | None:
        with self._connection() as conn:
            row = conn.execute('SELECT * FROM stt_artifacts WHERE owner=? AND run_id=? AND expires>=?', (owner, run_id, time.time())).fetchone()
        if row is None:
            return None
        result = dict(row)
        for field in ('audio_info', 'reference', 'review', 'annotations'):
            result[field] = json.loads(result[field]) if result[field] else None
        return result

    def save(self, owner: str, run_id: str, *, audio: bytes | None = None, content_type: str | None = None, audio_info: dict | None = None, reference: dict | None = None, review: dict | None = None, annotations: dict | None = None):
        with self._connection() as conn:
            now = time.time()
            # Updating a review must not revive expired audio or reference columns.
            conn.execute('DELETE FROM stt_artifacts WHERE owner=? AND run_id=? AND expires<?', (owner, run_id, now))
            conn.execute('INSERT INTO stt_artifacts(owner,run_id,expires) VALUES(?,?,?) ON CONFLICT(owner,run_id) DO UPDATE SET expires=excluded.expires', (owner, run_id, now + 86400))
            for field, value in (('audio', audio), ('content_type', content_type), ('audio_info', audio_info), ('reference', reference), ('review', review), ('annotations', annotations)):
                if value is not None:
                    encoded = json.dumps(value) if field in ('audio_info', 'reference', 'review', 'annotations') else value
                    conn.execute(f'UPDATE stt_artifacts SET {field}=? WHERE owner=? AND run_id=?', (encoded, owner, run_id))

    def delete_run(self, run_id: str):
        with self._connection() as conn:
            conn.execute('DELETE FROM stt_artifacts WHERE run_id=?', (run_id,))
