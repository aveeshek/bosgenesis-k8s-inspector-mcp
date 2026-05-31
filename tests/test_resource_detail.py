from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from bosgenesis_k8s_inspector_mcp.errors import PolicyDeniedError
from bosgenesis_k8s_inspector_mcp.operations import ops
from bosgenesis_k8s_inspector_mcp.server_mcp import k8s_get_resource


@pytest.fixture
def captured_audit(monkeypatch):
    records = []

    def emit(**kwargs):
        records.append(kwargs)
        return {
            "audit_id": f"audit-{len(records)}",
            "correlation_id": kwargs.get("correlation_id") or "corr-generated",
        }

    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.audit_logger.emit", emit)
    return records


@pytest.fixture(autouse=True)
def passthrough_serializer(monkeypatch):
    serializer = SimpleNamespace(sanitize_for_serialization=lambda obj: obj)
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.api_client", lambda: serializer)


def test_get_resource_allowed_deployment_returns_full_object(monkeypatch, captured_audit):
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "demo", "namespace": "bosgenesis"},
        "spec": {"template": {"spec": {"containers": [{"name": "app", "image": "demo:v1"}]}}},
        "status": {"readyReplicas": 1},
    }
    fake_apps = SimpleNamespace(
        read_namespaced_deployment=lambda name, namespace: deployment
    )
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.apps_v1", lambda: fake_apps)

    result = ops.get_resource("bosgenesis", "Deployment", "demo", actor="test", correlation_id="corr-1")

    assert result == {
        "status": "ok",
        "namespace": "bosgenesis",
        "kind": "Deployment",
        "name": "demo",
        "resource": deployment,
    }
    assert captured_audit[-1]["operation"] == "k8s_get_resource"
    assert captured_audit[-1]["status"] == "success"
    assert captured_audit[-1]["decision"] == "allowed"


def test_get_resource_allowed_service_returns_full_object(monkeypatch):
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "web", "namespace": "bosgenesis"},
        "spec": {"ports": [{"port": 80}], "selector": {"app": "web"}},
    }
    fake_core = SimpleNamespace(read_namespaced_service=lambda name, namespace: service)
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.core_v1", lambda: fake_core)

    result = ops.get_resource("bosgenesis", "Service", "web")

    assert result["resource"] == service


def test_get_resource_allowed_configmap_returns_full_object(monkeypatch):
    configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "settings", "namespace": "bosgenesis"},
        "data": {"app.yaml": "debug: true"},
    }
    fake_core = SimpleNamespace(read_namespaced_config_map=lambda name, namespace: configmap)
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.core_v1", lambda: fake_core)

    result = ops.get_resource("bosgenesis", "ConfigMap", "settings")

    assert result["resource"] == configmap


def test_get_resource_allowed_pvc_returns_full_object(monkeypatch):
    pvc = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": "data", "namespace": "bosgenesis"},
        "spec": {"resources": {"requests": {"storage": "10Gi"}}},
        "status": {"phase": "Bound"},
    }
    fake_core = SimpleNamespace(
        read_namespaced_persistent_volume_claim=lambda name, namespace: pvc
    )
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.core_v1", lambda: fake_core)

    result = ops.get_resource("bosgenesis", "PersistentVolumeClaim", "data")

    assert result["resource"] == pvc


@pytest.mark.parametrize("kind", ["Secret", "ClusterRole", "Namespace"])
def test_get_resource_blocked_kinds_are_denied(kind, captured_audit):
    with pytest.raises(PolicyDeniedError):
        ops.get_resource("bosgenesis", kind, "blocked", actor="test")

    assert captured_audit[-1]["operation"] == "k8s_get_resource"
    assert captured_audit[-1]["decision"] == "denied"
    assert captured_audit[-1]["status"] == "denied"


def test_get_resource_wrong_namespace_is_denied(captured_audit):
    with pytest.raises(PolicyDeniedError):
        ops.get_resource("default", "Deployment", "demo", actor="test")

    assert captured_audit[-1]["decision"] == "denied"
    assert captured_audit[-1]["namespace"] == "default"


def test_get_resource_missing_name_is_denied(captured_audit):
    with pytest.raises(PolicyDeniedError):
        ops.get_resource("bosgenesis", "Deployment", "", actor="test")

    assert captured_audit[-1]["decision"] == "denied"
    assert "name" in captured_audit[-1]["reason"].lower()


def test_get_resource_unknown_kind_is_denied(captured_audit):
    with pytest.raises(PolicyDeniedError):
        ops.get_resource("bosgenesis", "Widget", "demo", actor="test")

    assert captured_audit[-1]["decision"] == "denied"
    assert "not allowed" in captured_audit[-1]["reason"]


def test_get_resource_not_found_returns_controlled_error(monkeypatch, captured_audit):
    def read_missing(name, namespace):
        raise ApiException(status=404, reason="Not Found")

    fake_apps = SimpleNamespace(read_namespaced_deployment=read_missing)
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.operations.apps_v1", lambda: fake_apps)

    result = ops.get_resource("bosgenesis", "Deployment", "missing", actor="test")

    assert result == {
        "status": "not_found",
        "namespace": "bosgenesis",
        "kind": "Deployment",
        "name": "missing",
        "error": "resource_not_found",
    }
    assert captured_audit[-1]["operation"] == "k8s_get_resource"
    assert captured_audit[-1]["status"] == "failed"
    assert captured_audit[-1]["reason"] == "resource_not_found"


def test_mcp_get_resource_returns_structured_denial(captured_audit):
    result = k8s_get_resource(
        namespace="bosgenesis",
        kind="Secret",
        name="blocked",
        actor="test",
        correlation_id="corr-denied",
    )

    assert result == {
        "status": "denied",
        "namespace": "bosgenesis",
        "kind": "Secret",
        "name": "blocked",
        "error": "policy_denied",
        "message": "Kind 'Secret' is blocked by policy.",
    }
    assert captured_audit[-1]["operation"] == "k8s_get_resource"
    assert captured_audit[-1]["decision"] == "denied"
