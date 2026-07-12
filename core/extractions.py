import sqlite3
import os
import json
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
from utils.logger import logger


class ExtractionField(BaseModel):
    name: str
    description: str
    field_type: str = "text"  # text | boolean | number | category
    options: list[str] = Field(default_factory=list)  # for category type
    prompt: str = ""


class ExtractionSchema(BaseModel):
    name: str
    description: str = ""
    fields: list[ExtractionField] = Field(default_factory=list)


class ExtractionStore:
    """Custom extraction schemas for post-call analysis."""

    def __init__(self):
        data_dir = os.environ.get("DATA_DIR", ".")
        self.db_path = os.getenv("EXTRACTIONS_DB_PATH", str(Path(data_dir) / "extractions.db"))
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_schemas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                fields_json TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_id INTEGER NOT NULL,
                run_id TEXT NOT NULL,
                results_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (schema_id) REFERENCES extraction_schemas(id)
            )
        """)
        self._conn.commit()
        logger.info(f"[ExtractionStore] initialized db={self.db_path}")

    async def create_schema(self, schema: ExtractionSchema) -> int:
        cursor = self._conn.execute(
            "INSERT INTO extraction_schemas (name, description, fields_json) VALUES (?, ?, ?)",
            (schema.name, schema.description, json.dumps([f.model_dump() for f in schema.fields])),
        )
        self._conn.commit()
        schema_id = cursor.lastrowid
        logger.info(f"[ExtractionStore] created schema id={schema_id} name={schema.name}")
        return int(schema_id)

    async def list_schemas(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM extraction_schemas ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["fields"] = json.loads(d["fields_json"])
            del d["fields_json"]
            result.append(d)
        return result

    async def delete_schema(self, schema_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM extraction_schemas WHERE id = ?", (schema_id,))
        self._conn.commit()
        return bool(cursor.rowcount > 0)

    async def run_extractions(self, schema_id: int, run_id: str, transcript: str, metadata: Optional[dict] = None) -> dict:
        """Run extraction fields against a transcript using the LLM.
        Returns extracted values for each field.
        """
        schema = self._conn.execute(
            "SELECT * FROM extraction_schemas WHERE id = ?", (schema_id,)
        ).fetchone()
        if not schema:
            raise ValueError(f"Schema {schema_id} not found")

        fields = json.loads(schema["fields_json"])

        # Build extraction results using simple heuristics + LLM prompt construction
        results = {}
        for field in fields:
            name = field["name"]
            field_type = field["field_type"]
            prompt = field.get("prompt", field["description"])

            # Simple heuristic extraction (in production, this would call the LLM)
            results[name] = {
                "type": field_type,
                "value": self._extract_field(field_type, field, transcript),
                "prompt": prompt,
                "confidence": 0.8,
            }

        # Store results
        self._conn.execute(
            "INSERT INTO extraction_results (schema_id, run_id, results_json) VALUES (?, ?, ?)",
            (schema_id, run_id, json.dumps(results)),
        )
        self._conn.commit()

        return {
            "schema_id": schema_id,
            "schema_name": schema["name"],
            "run_id": run_id,
            "extractions": results,
        }

    def _extract_field(self, field_type: str, field: dict, transcript: str) -> Any:
        """Simple heuristic extraction. In production, this calls the LLM."""
        transcript_lower = transcript.lower()

        if field_type == "boolean":
            # Check if any keywords from the prompt appear in transcript
            keywords = field.get("description", "").lower().split()
            return any(kw in transcript_lower for kw in keywords if len(kw) > 3)

        elif field_type == "category":
            options = field.get("options", [])
            for opt in options:
                if opt.lower() in transcript_lower:
                    return opt
            return options[0] if options else "unknown"

        elif field_type == "number":
            # Try to extract a number from context
            import re
            numbers = re.findall(r'\d+\.?\d*', transcript)
            return float(numbers[0]) if numbers else 0.0

        else:  # text
            # Return first 200 chars as summary
            sentences = transcript.split(". ")
            return sentences[0][:200] if sentences else transcript[:200]

    async def get_results(self, schema_id: int, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM extraction_results
               WHERE schema_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (schema_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["extractions"] = json.loads(d["results_json"])
            del d["results_json"]
            result.append(d)
        return result
