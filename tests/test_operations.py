import pytest

from bosgenesis_k8s_inspector_mcp.errors import PolicyDeniedError
from bosgenesis_k8s_inspector_mcp.operations import ops


def test_delete_collection_requires_selector():
    with pytest.raises(PolicyDeniedError):
        ops.delete_collection(resource="configmaps", namespace="bosgenesis")
