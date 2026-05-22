import pytest

from bosgenesis_k8s_inspector_mcp.errors import PolicyDeniedError
from bosgenesis_k8s_inspector_mcp.policy import policy


def test_reject_wrong_namespace():
    with pytest.raises(PolicyDeniedError):
        policy.assert_namespace("default")


def test_allow_bosgenesis_namespace():
    assert policy.assert_namespace("bosgenesis") == "bosgenesis"


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
