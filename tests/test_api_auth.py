from fastapi.testclient import TestClient

from bosgenesis_k8s_inspector_mcp.config import config
from bosgenesis_k8s_inspector_mcp.server_fastapi import app


def test_mutating_endpoint_requires_configured_api_key(monkeypatch):
    monkeypatch.setattr(config.env, "api_key", "change-me-later")
    client = TestClient(app)

    response = client.post("/delete", json={"resource": "configmaps", "name": "demo"})

    assert response.status_code == 503
    assert "non-placeholder" in response.json()["detail"]


def test_mutating_endpoint_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(config.env, "api_key", "unit-test-key")
    client = TestClient(app)

    response = client.post("/delete", json={"resource": "configmaps", "name": "demo"})

    assert response.status_code == 401
