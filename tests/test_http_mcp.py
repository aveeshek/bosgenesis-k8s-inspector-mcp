from fastapi.routing import Mount

from bosgenesis_k8s_inspector_mcp.server_fastapi import app


def test_streamable_http_mcp_mount_exists():
    assert any(isinstance(route, Mount) and route.path == "" for route in app.routes)


def test_health_reports_mcp_endpoint():
    from fastapi.testclient import TestClient

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["mcp_endpoint"] == "/mcp"
