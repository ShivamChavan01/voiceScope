import os
import sqlite3
from pathlib import Path

from utils.logger import logger


class KnowledgeStore:
    """User-editable policy knowledge base backed by SQLite.

    The static `knowledge/business_policy.md` file remains the default seed.
    Entries added through this store are additive and merge with the file
    when the KnowledgeBase builds its ChromaDB index.
    """

    def __init__(self):
        data_dir = os.environ.get("DATA_DIR", ".")
        self.db_path = os.getenv("KNOWLEDGE_DB_PATH", str(Path(data_dir) / "knowledge.db"))
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()
        logger.info(f"[KnowledgeStore] initialized db={self.db_path}")

    async def list_entries(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, title, content, created_at FROM knowledge_entries ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    async def add_entry(self, title: str, content: str) -> int:
        title = (title or "").strip() or "Untitled policy"
        content = (content or "").strip()
        if not content:
            raise ValueError("Policy content cannot be empty")
        cursor = self._conn.execute(
            "INSERT INTO knowledge_entries (title, content) VALUES (?, ?)",
            (title, content),
        )
        self._conn.commit()
        entry_id = int(cursor.lastrowid)
        logger.info(f"[KnowledgeStore] added entry id={entry_id} title={title}")
        return entry_id

    async def delete_entry(self, entry_id: int) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM knowledge_entries WHERE id = ?", (entry_id,)
        )
        self._conn.commit()
        return bool(cursor.rowcount > 0)

    def get_chunks(self) -> list[str]:
        """Return user-added policy chunks for indexing.

        Each entry becomes one chunk labeled with its title so the analysis
        agent can cite which policy it matched.
        """
        rows = self._conn.execute(
            "SELECT title, content FROM knowledge_entries ORDER BY id"
        ).fetchall()
        chunks = []
        for r in rows:
            title = r["title"]
            content = r["content"]
            chunks.append(f"{title}:\n{content}")
        return chunks
