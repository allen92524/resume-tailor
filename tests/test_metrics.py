"""Tests for Prometheus metrics and the /metrics endpoint."""

import json
import os

from fastapi.testclient import TestClient

from src.models import JDAnalysis
from src.web import app

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_json_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class TestMetricsEndpoint:
    """Tests for the /metrics Prometheus endpoint."""

    def test_metrics_returns_200(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"] or \
               "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_contains_http_requests_total(self):
        # Hit an endpoint first to ensure the metric exists
        client.get("/api/v1/health")
        resp = client.get("/metrics")
        body = resp.text
        assert "http_requests_total" in body

    def test_metrics_contains_http_request_duration(self):
        client.get("/api/v1/health")
        resp = client.get("/metrics")
        body = resp.text
        assert "http_request_duration_seconds" in body

    def test_metrics_contains_active_requests(self):
        resp = client.get("/metrics")
        body = resp.text
        assert "http_active_requests" in body

    def test_metrics_contains_claude_api_metrics(self):
        resp = client.get("/metrics")
        body = resp.text
        assert "claude_api_calls_total" in body
        assert "claude_api_call_duration_seconds" in body

    def test_metrics_contains_resume_generation_counter(self):
        resp = client.get("/metrics")
        body = resp.text
        assert "resume_generations_total" in body

    def test_metrics_has_help_and_type_lines(self):
        resp = client.get("/metrics")
        body = resp.text
        assert "# HELP http_requests_total" in body
        assert "# TYPE http_requests_total counter" in body


class TestMetricsIncrement:
    """Tests that hitting endpoints actually increments counters."""

    def test_health_increments_request_counter(self):
        # Get the counter value before
        before = self._get_counter_value("http_requests_total", {
            "method": "GET",
            "endpoint": "/api/v1/health",
            "status_code": "200",
        })

        client.get("/api/v1/health")

        after = self._get_counter_value("http_requests_total", {
            "method": "GET",
            "endpoint": "/api/v1/health",
            "status_code": "200",
        })

        assert after == before + 1

    def test_post_endpoint_increments_counter(self, monkeypatch):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )

        before = self._get_counter_value("http_requests_total", {
            "method": "POST",
            "endpoint": "/api/v1/analyze-jd",
            "status_code": "200",
        })

        client.post("/api/v1/analyze-jd", json={"jd_text": "Some job description"})

        after = self._get_counter_value("http_requests_total", {
            "method": "POST",
            "endpoint": "/api/v1/analyze-jd",
            "status_code": "200",
        })

        assert after == before + 1

    def test_error_increments_with_error_status(self, monkeypatch):
        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: (_ for _ in ()).throw(RuntimeError("fail")),
        )

        before = self._get_counter_value("http_requests_total", {
            "method": "POST",
            "endpoint": "/api/v1/analyze-jd",
            "status_code": "500",
        })

        client.post("/api/v1/analyze-jd", json={"jd_text": "Some job description"})

        after = self._get_counter_value("http_requests_total", {
            "method": "POST",
            "endpoint": "/api/v1/analyze-jd",
            "status_code": "500",
        })

        assert after == before + 1

    def test_metrics_endpoint_not_tracked(self):
        """The /metrics endpoint itself should not be tracked by the middleware."""
        before = self._get_counter_value("http_requests_total", {
            "method": "GET",
            "endpoint": "/metrics",
            "status_code": "200",
        })

        client.get("/metrics")

        after = self._get_counter_value("http_requests_total", {
            "method": "GET",
            "endpoint": "/metrics",
            "status_code": "200",
        })

        assert after == before

    @staticmethod
    def _get_counter_value(metric_name: str, labels: dict) -> float:
        """Read the current value of a prometheus_client Counter."""
        from src.telemetry import REQUEST_COUNT

        try:
            return REQUEST_COUNT.labels(**labels)._value.get()
        except Exception:
            return 0.0
