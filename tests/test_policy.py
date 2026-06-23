import pytest

from bosgenesis_k8s_inspector_mcp.errors import PolicyDeniedError
from bosgenesis_k8s_inspector_mcp.config import config
from bosgenesis_k8s_inspector_mcp.policy import policy


def test_reject_wrong_namespace():
    with pytest.raises(PolicyDeniedError):
        policy.assert_namespace("default")


def test_allow_bosgenesis_namespace():
    assert policy.assert_namespace("bosgenesis") == "bosgenesis"


def test_runtime_namespace_switch_changes_policy_boundary():
    original = config._runtime_namespace
    try:
        config.set_runtime_namespace("signoz")

        assert policy.assert_namespace("signoz") == "signoz"
        assert policy.assert_namespace("bosgenesis") == "bosgenesis"
    finally:
        config._runtime_namespace = original


def test_reject_namespace_outside_allowlist():
    with pytest.raises(PolicyDeniedError, match="Allowed namespaces"):
        policy.assert_namespace("kube-system")


def test_read_only_namespace_blocks_writes():
    policy.assert_resource_allowed("pods", "list", namespace="signoz")

    with pytest.raises(PolicyDeniedError, match="does not allow writes"):
        policy.assert_resource_allowed("deployments", "patch", namespace="signoz")


def test_agent_testing_namespace_allows_target_writes():
    policy.assert_resource_allowed("deployments", "patch", namespace="agent-testing")


def test_serviceaccount_cleanup_allows_only_deletecollection():
    policy.assert_resource_allowed(
        "serviceaccounts",
        "deletecollection",
        namespace="agent-testing",
    )

    with pytest.raises(PolicyDeniedError, match="blocked"):
        policy.assert_resource_allowed("serviceaccounts", "create", namespace="agent-testing")

    with pytest.raises(PolicyDeniedError, match="does not allow writes"):
        policy.assert_resource_allowed("serviceaccounts", "deletecollection", namespace="signoz")


def test_reject_secret_manifest():
    manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "bad", "namespace": "bosgenesis"},
        "stringData": {"x": "y"},
    }
    with pytest.raises(PolicyDeniedError):
        policy.validate_manifest(manifest)


def test_reject_host_path_pod():
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "bad", "namespace": "bosgenesis"},
        "spec": {
            "containers": [{"name": "c", "image": "busybox"}],
            "volumes": [{"name": "host", "hostPath": {"path": "/"}}],
        },
    }
    with pytest.raises(PolicyDeniedError):
        policy.validate_manifest(manifest)


def test_allow_configmap_manifest():
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "ok", "namespace": "bosgenesis"},
        "data": {"a": "b"},
    }
    kind, resource, name = policy.validate_manifest(manifest)
    assert (kind, resource, name) == ("ConfigMap", "configmaps", "ok")


def test_allow_pvc_manifest():
    manifest = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": "data-ok", "namespace": "bosgenesis"},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "1Gi"}},
        },
    }

    kind, resource, name = policy.validate_manifest(manifest)

    assert (kind, resource, name) == ("PersistentVolumeClaim", "persistentvolumeclaims", "data-ok")


def test_reject_privileged_patch_payload():
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "app",
                            "securityContext": {"privileged": True},
                        }
                    ]
                }
            }
        }
    }
    with pytest.raises(PolicyDeniedError):
        policy.validate_patch_payload(patch)
