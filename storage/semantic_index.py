"""Private SQLite semantic index with local, fixed-model ONNX embeddings."""

import heapq
import json
import os
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
MODEL_VERSION = 'fastembed-0.9.1-minilm-l6-v2'
DIMENSIONS = 384


def index_path() -> Path:
    return Path(os.getenv('SEMANTIC_DB_PATH') or Path(os.getenv('DATA_DIR', '.')) / 'semantic' / 'index.sqlite')


def validate_legacy_migration() -> None:
    legacy = Path(os.getenv('CHROMA_PERSIST_DIR') or Path(os.getenv('DATA_DIR', '/tmp')) / 'chroma_db')
    if not (legacy / 'chroma.sqlite3').exists():
        return
    path = index_path()
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
            migrated = conn.execute('SELECT 1 FROM semantic_migrations WHERE model=? LIMIT 1', (MODEL_VERSION,)).fetchone()
    except sqlite3.Error:
        migrated = None
    if not migrated:
        raise RuntimeError('Legacy semantic index requires explicit offline export/import before startup')


@lru_cache(maxsize=1)
def embedding_model() -> TextEmbedding:
    return TextEmbedding(
        model_name=MODEL_NAME, threads=1,
        cache_dir=os.getenv('EMBEDDING_CACHE_DIR'),
        specific_model_path=os.getenv('SEMANTIC_MODEL_PATH'),
        local_files_only=os.getenv('EMBEDDING_LOCAL_ONLY', '').lower() == 'true',
    )


def embed(texts: list[str]) -> list[np.ndarray]:
    vectors = [np.asarray(vector, dtype='<f4') for vector in embedding_model().embed(texts)]
    if len(vectors) != len(texts):
        raise ValueError('Embedding count does not match documents')
    normalized = []
    for vector in vectors:
        norm = np.linalg.norm(vector.astype(np.float64))
        if vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all() or not np.isfinite(norm) or norm == 0:
            raise ValueError('Invalid embedding vector')
        normalized.append(np.asarray(vector / norm, dtype='<f4'))
    return normalized


class SemanticCollection:
    """A small-instance collection; cosine queries scan stored vectors exactly."""

    def __init__(self, name: str, path: Path | None = None):
        self.name = name
        self.path = path or index_path()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError('Semantic index must not be a symlink')
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with closing(self._connect()) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS semantic_documents (
                collection TEXT NOT NULL, id TEXT NOT NULL, document TEXT NOT NULL,
                metadata TEXT NOT NULL, embedding BLOB NOT NULL, model TEXT NOT NULL,
                PRIMARY KEY(collection, id))''')
            conn.commit()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute('PRAGMA secure_delete=ON')
        return conn

    def _write(self, ids: list[str], documents: list[str], metadatas: list[dict] | None, replace: bool):
        if len(ids) != len(documents) or len(set(ids)) != len(ids):
            raise ValueError('Document IDs must be unique and match documents')
        if any(not isinstance(i, str) or not i for i in ids) or any(not isinstance(d, str) or not d.strip() for d in documents):
            raise ValueError('Document IDs and text must be nonempty strings')
        metadata = metadatas if metadatas is not None else [{} for _ in ids]
        if len(metadata) != len(ids) or any(not isinstance(m, dict) for m in metadata):
            raise ValueError('Metadata must match documents')
        encoded = [json.dumps(m, allow_nan=False) for m in metadata]
        vectors = embed(documents) if documents else []
        rows = [(self.name, i, d, m, v.tobytes(), MODEL_VERSION)
                for i, d, m, v in zip(ids, documents, encoded, vectors, strict=True)]
        with closing(self._connect()) as conn, conn:
            if replace:
                conn.execute('DELETE FROM semantic_documents WHERE collection=?', (self.name,))
            conn.executemany('INSERT INTO semantic_documents VALUES(?,?,?,?,?,?) '
                'ON CONFLICT(collection,id) DO UPDATE SET document=excluded.document, '
                'metadata=excluded.metadata, embedding=excluded.embedding, model=excluded.model', rows)

    def upsert(self, *, ids: list[str], documents: list[str], metadatas: list[dict] | None = None):
        self._write(ids, documents, metadatas, replace=False)

    def replace(self, *, ids: list[str], documents: list[str], metadatas: list[dict] | None = None):
        self._write(ids, documents, metadatas, replace=True)

    def get(self) -> dict:
        with closing(self._connect()) as conn:
            rows = conn.execute('SELECT id,document,metadata FROM semantic_documents WHERE collection=? ORDER BY id', (self.name,)).fetchall()
        return {'ids': [r[0] for r in rows], 'documents': [r[1] for r in rows],
                'metadatas': [json.loads(r[2]) for r in rows]}

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute('SELECT COUNT(*) FROM semantic_documents WHERE collection=?', (self.name,)).fetchone()[0])

    def delete(self, *, ids: list[str]):
        with closing(self._connect()) as conn, conn:
            conn.executemany('DELETE FROM semantic_documents WHERE collection=? AND id=?', [(self.name, i) for i in ids])

    def query(self, *, query_texts: list[str], n_results: int = 3) -> dict:
        if isinstance(n_results, bool) or not isinstance(n_results, int) or not 1 <= n_results <= 200:
            raise ValueError('Result limit must be between 1 and 200')
        if not self.count():
            return {'documents': [[] for _ in query_texts]}
        results = []
        for query in embed(query_texts):
            def scores(rows):
                for identity, document, blob, model in rows:
                    vector = np.frombuffer(blob, dtype='<f4')
                    if model != MODEL_VERSION or vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
                        raise ValueError('Stored embedding requires a verified reindex')
                    precise = vector.astype(np.float64)
                    score = float(np.dot(query.astype(np.float64), precise) / (np.linalg.norm(query) * np.linalg.norm(precise)))
                    yield -score, identity, document
            with closing(self._connect()) as conn:
                rows = conn.execute('SELECT id,document,embedding,model FROM semantic_documents WHERE collection=?', (self.name,))
                results.append([r[2] for r in heapq.nsmallest(n_results, scores(rows))])
        return {'documents': results}
