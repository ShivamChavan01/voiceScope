import os

os.environ["VALID_API_KEYS"] = "test-key"

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestRootEndpoint:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "VoiceScope"
        assert "providers" in data


class TestAnalyzeEndpoint:
    def test_analyze_no_file(self):
        response = client.post("/api/v1/analyze", headers={"X-API-Key": "test-key"})
        assert response.status_code == 422

    def test_analyze_invalid_file_type(self):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.txt", b"content", "text/plain")},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400


class TestAnalyzeTextEndpoint:
    def test_analyze_text_empty(self):
        response = client.post(
            "/api/v1/analyze-text",
            json={"transcript": ""},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 422

    def test_status(self):
        response = client.get("/api/v1/status", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        data = response.json()
        assert "llm_provider" in data
        assert "llm_backups_configured" in data
        assert "OPENROUTER_API_KEY" not in str(data)
        assert "GROQ_API_KEY" not in str(data)
