from __future__ import annotations

from typing import Any

from .config import config
from .errors import PolicyDeniedError


class NamespacePolicy:
    def __init__(self) -> None:
        self.policy = config.policy
        self.allowed_namespace = config.namespace
        self.blocked_resources = set(self.policy.get("blocked_resources", []))
        self.blocked_subresources = set(self.policy.get("blocked_subresources", []))
        self.allowed_read_resources = set(self.policy.get("allowed_read_resources", []))
        self.allowed_write_resources = set(self.policy.get("allowed_write_resources", []))
        self.mutation_safety = self.policy.get("mutation_safety", {})

    def assert_namespace(self, namespace: str | None) -> str:
        if not namespace:
            raise PolicyDeniedError("Namespace is required.")
        if namespace != self.allowed_namespace:
            raise PolicyDeniedError(
                f"Namespace '{namespace}' is not allowed. Only '{self.allowed_namespace}' is permitted."
            )
        return namespace

    def assert_resource_allowed(self, resource: str, verb: str) -> None:
        resource = resource.lower()
        verb = verb.lower()
        if resource in self.blocked_resources or resource in self.blocked_subresources:
            raise PolicyDeniedError(f"Resource '{resource}' is blocked by policy.")
        if verb in {"get", "list", "watch", "read", "logs"}:
            if resource not in self.allowed_read_resources:
                raise PolicyDeniedError(f"Read access to resource '{resource}' is not allowed.")
        elif verb in {"create", "update", "patch", "delete", "apply", "scale", "restart"}:
            if resource not in self.allowed_write_resources:
                raise PolicyDeniedError(f"Write access to resource '{resource}' is not allowed.")
        else:
            raise PolicyDeniedError(f"Verb '{verb}' is not supported.")

    def validate_manifest(self, manifest: dict[str, Any]) -> tuple[str, str, str]:
        if not isinstance(manifest, dict):
            raise PolicyDeniedError("Manifest must be a Kubernetes object dictionary.")

        kind = str(manifest.get("kind", "")).strip()
        api_version = str(manifest.get("apiVersion", "")).strip()
        metadata = manifest.get("metadata") or {}
        namespace = metadata.get("namespace")
        name = metadata.get("name")

        if not kind or not api_version:
            raise PolicyDeniedError("Manifest must include apiVersion and kind.")
        if not name:
            raise PolicyDeniedError("Manifest metadata.name is required.")

        self.assert_namespace(namespace)
        resource = kind_to_resource(kind)
        self.assert_resource_allowed(resource, "apply")

        if self.mutation_safety.get("reject_cluster_scoped_objects", True):
            if kind in {
                "Namespace",
                "Node",
                "PersistentVolume",
                "ClusterRole",
                "ClusterRoleBinding",
                "CustomResourceDefinition",
            }:
                raise PolicyDeniedError(f"Cluster-scoped kind '{kind}' is blocked.")

        self._validate_pod_security(manifest)
        return kind, resource, name

    def _validate_pod_security(self, manifest: dict[str, Any]) -> None:
        kind = str(manifest.get("kind", ""))
        specs: list[dict[str, Any]] = []

        if kind == "Pod":
            specs.append(manifest.get("spec", {}) or {})
        elif kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
            specs.append(
                (((manifest.get("spec", {}) or {}).get("template", {}) or {}).get("spec", {}) or {})
            )
        elif kind == "CronJob":
            specs.append(
                (
                    (((manifest.get("spec", {}) or {}).get("jobTemplate", {}) or {}).get("spec", {}) or {})
                    .get("template", {})
                    .get("spec", {})
                    or {}
                )
            )

        for spec in specs:
            if self.mutation_safety.get("reject_host_network", True) and spec.get("hostNetwork"):
                raise PolicyDeniedError("hostNetwork is blocked by policy.")
            if self.mutation_safety.get("reject_host_pid", True) and spec.get("hostPID"):
                raise PolicyDeniedError("hostPID is blocked by policy.")
            if self.mutation_safety.get("reject_host_ipc", True) and spec.get("hostIPC"):
                raise PolicyDeniedError("hostIPC is blocked by policy.")
            if self.mutation_safety.get("reject_service_account_override", True) and spec.get(
                "serviceAccountName"
            ):
                raise PolicyDeniedError("serviceAccountName override is blocked by policy.")
            if self.mutation_safety.get("default_automount_service_account_token", False) is False:
                # We do not reject missing field; we enforce by mutating below in operations where possible.
                pass
            if self.mutation_safety.get("reject_host_path_volumes", True):
                for vol in spec.get("volumes", []) or []:
                    if "hostPath" in vol:
                        raise PolicyDeniedError("hostPath volumes are blocked by policy.")
            if self.mutation_safety.get("reject_privileged_containers", True):
                for c in (spec.get("containers", []) or []) + (spec.get("initContainers", []) or []):
                    sc = c.get("securityContext") or {}
                    if sc.get("privileged") is True:
                        raise PolicyDeniedError("Privileged containers are blocked by policy.")


def kind_to_resource(kind: str) -> str:
    mapping = {
        "Pod": "pods",
        "Service": "services",
        "ConfigMap": "configmaps",
        "PersistentVolumeClaim": "persistentvolumeclaims",
        "Deployment": "deployments",
        "ReplicaSet": "replicasets",
        "StatefulSet": "statefulsets",
        "DaemonSet": "daemonsets",
        "Job": "jobs",
        "CronJob": "cronjobs",
        "Ingress": "ingresses",
        "Event": "events",
    }
    if kind not in mapping:
        raise PolicyDeniedError(f"Kind '{kind}' is not supported by this MCP server.")
    return mapping[kind]


policy = NamespacePolicy()
