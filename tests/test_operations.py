from types import SimpleNamespace

import pytest

from bosgenesis_k8s_inspector_mcp.errors import PolicyDeniedError
from bosgenesis_k8s_inspector_mcp.operations import ops


def test_delete_collection_requires_selector():
    with pytest.raises(PolicyDeniedError):
        ops.delete_collection(resource="configmaps", namespace="bosgenesis")


def test_list_pvcs_returns_namespace_scoped_summaries(monkeypatch):
    pvc = SimpleNamespace(
        metadata=SimpleNamespace(
            name="data-demo",
            namespace="bosgenesis",
            creation_timestamp=None,
        ),
        spec=SimpleNamespace(
            storage_class_name="local-path",
            volume_name="pvc-123",
            access_modes=["ReadWriteOnce"],
            resources=SimpleNamespace(requests={"storage": "10Gi"}),
            volume_mode="Filesystem",
        ),
        status=SimpleNamespace(
            phase="Bound",
            capacity={"storage": "10Gi"},
        ),
    )
    fake_core = SimpleNamespace(
        list_namespaced_persistent_volume_claim=lambda namespace: SimpleNamespace(items=[pvc])
    )
    monkeypatch.setattr(
        "bosgenesis_k8s_inspector_mcp.operations.core_v1",
        lambda: fake_core,
    )

    result = ops.list_pvcs(actor="test")

    assert result == [
        {
            "name": "data-demo",
            "namespace": "bosgenesis",
            "phase": "Bound",
            "storage_class": "local-path",
            "volume_name": "pvc-123",
            "access_modes": ["ReadWriteOnce"],
            "requested_storage": "10Gi",
            "capacity": "10Gi",
            "volume_mode": "Filesystem",
            "created_at": None,
        }
    ]


def test_list_configmaps_returns_key_summaries_without_values(monkeypatch):
    configmap = SimpleNamespace(
        metadata=SimpleNamespace(
            name="app-config",
            namespace="bosgenesis",
            labels={"app": "demo"},
            annotations={},
            creation_timestamp=None,
        ),
        data={"PASSWORD_LIKE_NAME": "not-returned", "app.yaml": "debug: true"},
        binary_data={"cert.bin": "AA=="},
    )
    fake_core = SimpleNamespace(
        list_namespaced_config_map=lambda namespace: SimpleNamespace(items=[configmap])
    )
    monkeypatch.setattr(
        "bosgenesis_k8s_inspector_mcp.operations.core_v1",
        lambda: fake_core,
    )

    result = ops.list_configmaps(actor="test")

    assert result == [
        {
            "name": "app-config",
            "namespace": "bosgenesis",
            "data_keys": ["PASSWORD_LIKE_NAME", "app.yaml"],
            "binary_data_keys": ["cert.bin"],
            "data_key_count": 2,
            "binary_data_key_count": 1,
            "labels": {"app": "demo"},
            "annotations": {},
            "created_at": None,
        }
    ]
    assert "not-returned" not in str(result)


def test_get_configmap_returns_data_only_when_requested(monkeypatch):
    configmap = SimpleNamespace(
        metadata=SimpleNamespace(
            name="app-config",
            namespace="bosgenesis",
            labels={},
            annotations={},
            creation_timestamp=None,
        ),
        data={"app.yaml": "debug: true"},
        binary_data={},
    )
    fake_core = SimpleNamespace(
        read_namespaced_config_map=lambda name, namespace: configmap
    )
    monkeypatch.setattr(
        "bosgenesis_k8s_inspector_mcp.operations.core_v1",
        lambda: fake_core,
    )

    hidden = ops.get_configmap("app-config", actor="test")
    visible = ops.get_configmap("app-config", include_data=True, actor="test")

    assert "data" not in hidden
    assert visible["data"] == {"app.yaml": "debug: true"}


def test_create_pvc_rejects_non_pvc_manifest():
    with pytest.raises(PolicyDeniedError):
        ops.create_pvc(
            manifest={
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "not-a-pvc", "namespace": "bosgenesis"},
            },
            dry_run=True,
        )
