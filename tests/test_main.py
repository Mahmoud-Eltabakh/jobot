"""Tests for main FastAPI application endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Verify /health endpoint returns expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Jobot"
    assert data["version"] == "0.1.0"
