import pytest
from unittest.mock import patch, AsyncMock
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
        response = client.post("/api/v1/analyze")
        assert response.status_code == 422

    def test_analyze_invalid_file_type(self):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert response.status_code == 400
