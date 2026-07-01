import os
import pytest

os.environ["VALID_API_KEYS"] = "test-key"

from fastapi.testclient import TestClient
from main import app
from core.qa import QAStore, QACohort, ResolutionCriterion
from core.extractions import ExtractionStore, ExtractionSchema, ExtractionField
from utils.guardrails import ContentGuardrails


client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


# ─── Monitoring Tests ─────────────────────────────────────────────────


class TestMonitoringMetrics:
    def test_get_metrics_empty(self):
        response = client.get("/api/v1/monitoring/metrics", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "total_calls" in data
        assert "hallucination_rate" in data

    def test_get_metrics_with_window(self):
        response = client.get("/api/v1/monitoring/metrics?window_minutes=30", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["window_minutes"] == 30


class TestAlertRules:
    def test_create_alert_rule(self):
        response = client.post(
            "/api/v1/monitoring/alerts",
            json={
                "name": "High hallucination rate",
                "metric": "hallucination_rate",
                "comparator": "gt",
                "threshold": 0.3,
                "window_minutes": 60,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "created"
        assert "rule_id" in response.json()

    def test_list_alert_rules(self):
        response = client.get("/api/v1/monitoring/alerts", headers=HEADERS)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_delete_alert_rule_not_found(self):
        response = client.delete("/api/v1/monitoring/alerts/99999", headers=HEADERS)
        assert response.status_code == 404


class TestAlertChecking:
    def test_check_alerts_empty(self):
        response = client.post("/api/v1/monitoring/check", headers=HEADERS)
        assert response.status_code == 200
        assert "triggered" in response.json()


# ─── QA System Tests ──────────────────────────────────────────────────


class TestQACohorts:
    def setup_method(self):
        from api.routes import get_qa_store
        store = get_qa_store()
        store._conn.execute("DELETE FROM qa_cohorts")
        store._conn.execute("DELETE FROM qa_results")
        store._conn.commit()

    def test_create_cohort(self):
        response = client.post(
            "/api/v1/qa/cohorts",
            json={
                "name": "Sales QA Integration",
                "platform_filter": "vapi",
                "sampling_pct": 20.0,
                "criteria": [
                    {"name": "resolved", "description": "Was the issue resolved?", "weight": 2.0},
                    {"name": "polite", "description": "Was the agent polite?", "weight": 1.0},
                ],
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "created"

    def test_list_cohorts(self):
        response = client.get("/api/v1/qa/cohorts", headers=HEADERS)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_score_call(self):
        # Create a cohort first
        create_resp = client.post(
            "/api/v1/qa/cohorts",
            json={"name": "Score Test Integration", "criteria": [{"name": "test", "description": "test", "weight": 1.0}]},
            headers=HEADERS,
        )
        cohort_id = create_resp.json()["cohort_id"]

        # Score a call
        response = client.post(
            f"/api/v1/qa/cohorts/{cohort_id}/score",
            json={"run_id": "test-run-001", "metrics": {"quality_score": 85, "outcome": "resolved"}},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "overall_score" in response.json()
        assert "passed" in response.json()

    def test_score_call_invalid_cohort(self):
        response = client.post(
            "/api/v1/qa/cohorts/99999/score",
            json={"run_id": "test", "metrics": {}},
            headers=HEADERS,
        )
        assert response.status_code == 404

    def test_get_cohort_results(self):
        response = client.get("/api/v1/qa/cohorts/1/results", headers=HEADERS)
        assert response.status_code == 200
        assert "total_scored" in response.json()


# ─── Extraction Schema Tests ──────────────────────────────────────────


class TestExtractionSchemas:
    def setup_method(self):
        from api.routes import get_extraction_store
        store = get_extraction_store()
        store._conn.execute("DELETE FROM extraction_schemas")
        store._conn.execute("DELETE FROM extraction_results")
        store._conn.commit()

    def test_create_schema(self):
        response = client.post(
            "/api/v1/extractions/schemas",
            json={
                "name": "Call Outcome Integration",
                "description": "Extract call outcome data",
                "fields": [
                    {"name": "resolved", "description": "Was the issue resolved?", "field_type": "boolean"},
                    {"name": "sentiment", "description": "Customer sentiment", "field_type": "category", "options": ["positive", "negative", "neutral"]},
                ],
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "created"

    def test_list_schemas(self):
        response = client.get("/api/v1/extractions/schemas", headers=HEADERS)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_run_extractions(self):
        # Create schema
        create_resp = client.post(
            "/api/v1/extractions/schemas",
            json={
                "name": "Test Extraction Integration",
                "fields": [{"name": "summary", "description": "Call summary", "field_type": "text"}],
            },
            headers=HEADERS,
        )
        schema_id = create_resp.json()["schema_id"]

        # Run extractions
        response = client.post(
            f"/api/v1/extractions/schemas/{schema_id}/run",
            json={"run_id": "test-001", "transcript": "Agent: Hello. Customer: I need help with billing."},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "extractions" in response.json()

    def test_run_extractions_invalid_schema(self):
        response = client.post(
            "/api/v1/extractions/schemas/99999/run",
            json={"run_id": "test", "transcript": "test"},
            headers=HEADERS,
        )
        assert response.status_code == 404


# ─── Guardrails Tests ─────────────────────────────────────────────────


class TestGuardrails:
    def test_get_status(self):
        response = client.get("/api/v1/guardrails/status", headers=HEADERS)
        assert response.status_code == 200
        assert "enabled_categories" in response.json()

    def test_check_input_safe(self):
        response = client.post(
            "/api/v1/guardrails/check",
            json={"text": "Hello, I need help with my order", "check_type": "input"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["blocked"] is False

    def test_check_input_harmful(self):
        response = client.post(
            "/api/v1/guardrails/check",
            json={"text": "I want to kill myself", "check_type": "input"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["blocked"] is True
        assert "self_harm" in response.json()["flagged_categories"]

    def test_check_output_safe(self):
        response = client.post(
            "/api/v1/guardrails/check",
            json={"text": "Your order has been shipped", "check_type": "output"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["blocked"] is False

    def test_redact_pii(self):
        response = client.post(
            "/api/v1/guardrails/check",
            json={"text": "My email is john@example.com and phone is 555-123-4567", "check_type": "redact_pii"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "REDACTED" in response.json()["redacted_text"]
        assert len(response.json()["redactions"]) >= 2

    def test_invalid_check_type(self):
        response = client.post(
            "/api/v1/guardrails/check",
            json={"text": "test", "check_type": "invalid"},
            headers=HEADERS,
        )
        assert response.status_code == 400


# ─── Guardrails Unit Tests ────────────────────────────────────────────


class TestGuardrailsUnit:
    def setup_method(self):
        self.g = ContentGuardrails()

    def test_self_harm_detection(self):
        result = self.g.check_input("I want to kill myself")
        assert result.blocked is True
        assert "self_harm" in result.flagged_categories

    def test_violence_detection(self):
        result = self.g.check_input("I'm going to shoot someone")
        assert result.blocked is True
        assert "violence" in result.flagged_categories

    def test_safe_input(self):
        result = self.g.check_input("Can you help me with my order?")
        assert result.blocked is False

    def test_pii_redaction_email(self):
        redacted, redactions = self.g.redact_pii("Contact me at test@example.com")
        assert "REDACTED_EMAIL" in redacted
        assert any(r["type"] == "email" for r in redactions)

    def test_pii_redaction_phone(self):
        redacted, redactions = self.g.redact_pii("Call me at 555-123-4567")
        assert "REDACTED_PHONE" in redacted

    def test_pii_redaction_ssn(self):
        redacted, redactions = self.g.redact_pii("SSN is 123-45-6789")
        assert "REDACTED_SSN" in redacted


# ─── QA Store Unit Tests ──────────────────────────────────────────────


class TestQAStoreUnit:
    def setup_method(self):
        os.environ["QA_DB_PATH"] = ":memory:"
        self.store = QAStore()

    @pytest.mark.asyncio
    async def test_create_and_list_cohort(self):
        cohort = QACohort(
            name="Test Cohort",
            criteria=[ResolutionCriterion(name="resolved", description="Was resolved?", weight=2.0)],
        )
        cohort_id = await self.store.create_cohort(cohort)
        assert cohort_id > 0

        cohorts = await self.store.list_cohorts()
        assert len(cohorts) >= 1
        assert cohorts[0]["name"] == "Test Cohort"

    @pytest.mark.asyncio
    async def test_score_call(self):
        cohort = QACohort(
            name="Score Test",
            criteria=[ResolutionCriterion(name="test", description="test", weight=1.0)],
        )
        cohort_id = await self.store.create_cohort(cohort)

        result = await self.store.score_call(
            cohort_id, "run-001", {"quality_score": 85, "outcome": "resolved"}
        )
        assert "overall_score" in result
        assert "passed" in result


# ─── Extraction Store Unit Tests ──────────────────────────────────────


class TestExtractionStoreUnit:
    def setup_method(self):
        os.environ["EXTRACTIONS_DB_PATH"] = ":memory:"
        self.store = ExtractionStore()

    @pytest.mark.asyncio
    async def test_create_and_list_schema(self):
        schema = ExtractionSchema(
            name="Test Schema",
            fields=[ExtractionField(name="summary", description="Summary", field_type="text")],
        )
        schema_id = await self.store.create_schema(schema)
        assert schema_id > 0

        schemas = await self.store.list_schemas()
        assert len(schemas) >= 1

    @pytest.mark.asyncio
    async def test_run_extractions(self):
        schema = ExtractionSchema(
            name="Test",
            fields=[ExtractionField(name="resolved", description="resolved", field_type="boolean")],
        )
        schema_id = await self.store.create_schema(schema)

        result = await self.store.run_extractions(
            schema_id, "run-001", "The issue has been resolved. Customer is happy."
        )
        assert "extractions" in result
        assert result["extractions"]["resolved"]["value"] is True
