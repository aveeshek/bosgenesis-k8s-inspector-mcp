from fastapi.routing import Mount

from bosgenesis_k8s_inspector_mcp.server_fastapi import app


def test_streamable_http_mcp_mount_exists():
    assert any(isinstance(route, Mount) and route.path == "" for route in app.routes)


def test_health_reports_mcp_endpoint():
    from fastapi.testclient import TestClient

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["mcp_endpoint"] == "/mcp"


def test_pvc_routes_exist():
    paths = {route.path for route in app.routes}

    assert "/pvcs" in paths
    assert "/pvcs/{pvc_name}" in paths


def test_resource_detail_route_exists():
    paths = {route.path for route in app.routes}

    assert "/resource" in paths


def test_resource_detail_openapi_schema_is_strict():
    from fastapi.testclient import TestClient

    schema = TestClient(app).get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["GetResourceRequest"]

    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {"namespace", "kind", "name"}
    assert request_schema["properties"]["kind"]["enum"] == [
        "ConfigMap",
        "Service",
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Job",
        "CronJob",
        "PersistentVolumeClaim",
        "Ingress",
    ]
