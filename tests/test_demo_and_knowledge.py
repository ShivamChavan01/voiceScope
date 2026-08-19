import os
import tempfile

import pytest

os.environ["VALID_API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = ""

import middleware.auth  # noqa: E402

middleware.auth._VALID_KEYS = frozenset(["test-key"])

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture(autouse=True)
def _isolate_stores(monkeypatch):
    """Point every store at a fresh temp dir, scoped to this test only."""
    import api.routes as routes

    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("MONITORING_DB_PATH", os.path.join(tmp, "monitoring.db"))
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", os.path.join(tmp, "knowledge.db"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", os.path.join(tmp, "chroma"))
    routes.get_monitoring_store.cache_clear()
    routes.get_knowledge_store.cache_clear()
    routes.get_pipeline.cache_clear()
    yield


class TestDemoSeed:
    def test_seed_populates_runs(self):
        response = client.post("/api/v1/demo/seed", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["seeded"] >= 8

    def test_seeded_run_has_evidence(self):
        client.post("/api/v1/demo/seed", headers=HEADERS)
        response = client.get("/api/v1/runs/demo-003", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["hallucination_detected"] == 1
        assert data["hallucination_evidence"]
        assert data["policy_evidence"]


class TestKnowledgeAPI:
    def test_add_and_list(self):
        add = client.post(
            "/api/v1/knowledge",
            json={"title": "Test Policy", "content": "Refunds take 10 days."},
            headers=HEADERS,
        )
        assert add.status_code == 200
        assert add.json()["entry_id"] >= 1

        entries = client.get("/api/v1/knowledge", headers=HEADERS).json()
        assert any(e["title"] == "Test Policy" for e in entries)

    def test_add_requires_content(self):
        response = client.post(
            "/api/v1/knowledge", json={"title": "Empty", "content": "  "}, headers=HEADERS
        )
        assert response.status_code == 400

    def test_delete(self):
        add = client.post(
            "/api/v1/knowledge",
            json={"title": "Doomed", "content": "This will be deleted."},
            headers=HEADERS,
        )
        entry_id = add.json()["entry_id"]
        delete = client.delete(f"/api/v1/knowledge/{entry_id}", headers=HEADERS)
        assert delete.status_code == 200
        entries = client.get("/api/v1/knowledge", headers=HEADERS).json()
        assert all(e["id"] != entry_id for e in entries)
