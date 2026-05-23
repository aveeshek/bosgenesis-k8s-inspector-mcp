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
