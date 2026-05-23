from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient

from .audit import audit_logger
from .config import config
from .errors import KubernetesOperationError, PolicyDeniedError
from .k8s_client import api_client, apps_v1, batch_v1, core_v1, networking_v1
from .models import OperationResponse
from .policy import policy


RESOURCE_DEFS: dict[str, tuple[str, str]] = {
    "pods": ("v1", "Pod"),
    "services": ("v1", "Service"),
    "configmaps": ("v1", "ConfigMap"),
    "persistentvolumeclaims": ("v1", "PersistentVolumeClaim"),
    "deployments": ("apps/v1", "Deployment"),
    "statefulsets": ("apps/v1", "StatefulSet"),
    "daemonsets": ("apps/v1", "DaemonSet"),
    "jobs": ("batch/v1", "Job"),
    "cronjobs": ("batch/v1", "CronJob"),
    "ingresses": ("networking.k8s.io/v1", "Ingress"),
}

SECRET_NAME_PREFIX = "bosgenesis-mcp-"
SECRET_OWNER_LABEL = "bosgenesis.io/secret-owner"
SECRET_MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
SECRET_CORRELATION_ANNOTATION = "bosgenesis.io/correlation-id"
SECRET_EXPIRES_AT_ANNOTATION = "bosgenesis.io/expires-at"
SECRET_MANAGED_BY = "bosgenesis-k8s-inspector-mcp"
_owned_secret_sessions: dict[str, dict[str, Any]] = {}


class KubernetesOperations:
    def __init__(self) -> None:
        self.namespace = config.namespace

    def namespace_summary(self, actor: str = "codex") -> dict[str, Any]:
        namespace = policy.assert_namespace(self.namespace)
        with audit_logger.span("k8s.namespace_summary", {"k8s.namespace": namespace}):
            pods = self.list_pods(actor=actor)
            services = self.list_services(actor=actor)
            deployments = self.list_deployments(actor=actor)
            ingresses = self.list_ingresses(actor=actor)
            pvcs = self.list_pvcs(actor=actor)
            summary = {
                "namespace": namespace,
                "counts": {
                    "pods": len(pods),
                    "services": len(services),
                    "deployments": len(deployments),
                    "ingresses": len(ingresses),
                    "persistentvolumeclaims": len(pvcs),
                },
                "pods_by_phase": {},
            }
            for pod in pods:
                phase = pod.get("phase", "Unknown")
                summary["pods_by_phase"][phase] = summary["pods_by_phase"].get(phase, 0) + 1
            audit_logger.emit(
                action="summary",
                resource="namespace",
                namespace=namespace,
                status="success",
                actor=actor,
                response_summary=summary,
            )
            return summary

    def list_pods(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("pods", "list")
        with audit_logger.span("k8s.list_pods", {"k8s.namespace": self.namespace}):
            items = core_v1().list_namespaced_pod(namespace=self.namespace).items
            pods = [self._pod_summary(p) for p in items]
            audit_logger.emit(
                action="list",
                resource="pods",
                namespace=self.namespace,
                status="success",
                actor=actor,
                tool="k8s_list_pods",
                response_summary={"count": len(pods)},
            )
            return pods

    def describe_pod(self, name: str, actor: str = "codex") -> dict[str, Any]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("pods", "get")
        with audit_logger.span("k8s.describe_pod", {"k8s.namespace": self.namespace, "k8s.pod": name}):
            pod = core_v1().read_namespaced_pod(name=name, namespace=self.namespace)
            result = api_client().sanitize_for_serialization(pod)
            audit_logger.emit(
                action="get",
                resource="pods",
                namespace=self.namespace,
                name=name,
                status="success",
                actor=actor,
                tool="k8s_describe_pod",
                response_summary={"phase": pod.status.phase},
            )
            return result

    def pod_logs(self, name: str, tail_lines: int = 200, actor: str = "codex") -> dict[str, Any]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("pods/log", "logs")
        with audit_logger.span("k8s.pod_logs", {"k8s.namespace": self.namespace, "k8s.pod": name}):
            logs = core_v1().read_namespaced_pod_log(
                name=name,
                namespace=self.namespace,
                tail_lines=min(max(tail_lines, 1), 1000),
                timestamps=True,
            )
            audit_logger.emit(
                action="logs",
                resource="pods/log",
                namespace=self.namespace,
                name=name,
                status="success",
                actor=actor,
                tool="k8s_get_pod_logs",
                response_summary={"tail_lines": tail_lines, "bytes": len(logs.encode("utf-8"))},
            )
            return {"namespace": self.namespace, "pod": name, "tail_lines": tail_lines, "logs": logs}

    def list_services(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("services", "list")
        items = core_v1().list_namespaced_service(namespace=self.namespace).items
        result = [
            {
                "name": s.metadata.name,
                "type": s.spec.type,
                "cluster_ip": s.spec.cluster_ip,
                "ports": [
                    {"name": p.name, "port": p.port, "target_port": str(p.target_port), "protocol": p.protocol}
                    for p in (s.spec.ports or [])
                ],
            }
            for s in items
        ]
        audit_logger.emit(action="list", resource="services", namespace=self.namespace, status="success", actor=actor, tool="k8s_list_services", response_summary={"count": len(result)})
        return result

    def list_configmaps(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("configmaps", "list")
        items = core_v1().list_namespaced_config_map(namespace=self.namespace).items
        result = [self._configmap_summary(configmap) for configmap in items]
        audit_logger.emit(
            action="list",
            resource="configmaps",
            namespace=self.namespace,
            status="success",
            actor=actor,
            tool="k8s_list_configmaps",
            response_summary={"count": len(result)},
        )
        return result

    def get_configmap(
        self,
        name: str,
        include_data: bool = False,
        actor: str = "codex",
    ) -> dict[str, Any]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("configmaps", "get")
        with audit_logger.span(
            "k8s.get_configmap",
            {"k8s.namespace": self.namespace, "k8s.configmap": name},
        ):
            configmap = core_v1().read_namespaced_config_map(name=name, namespace=self.namespace)
            result = self._configmap_summary(configmap)
            if include_data:
                result["data"] = configmap.data or {}
                result["binary_data"] = configmap.binary_data or {}
            audit_logger.emit(
                action="get",
                resource="configmaps",
                namespace=self.namespace,
                name=name,
                status="success",
                actor=actor,
                tool="k8s_get_configmap",
                response_summary={
                    "data_keys": result["data_keys"],
                    "binary_data_keys": result["binary_data_keys"],
                    "include_data": include_data,
                },
            )
            return result

    def list_pvcs(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("persistentvolumeclaims", "list")
        items = core_v1().list_namespaced_persistent_volume_claim(namespace=self.namespace).items
        result = [self._pvc_summary(pvc) for pvc in items]
        audit_logger.emit(
            action="list",
            resource="persistentvolumeclaims",
            namespace=self.namespace,
            status="success",
            actor=actor,
            tool="k8s_list_pvcs",
            response_summary={"count": len(result)},
        )
        return result

    def describe_pvc(self, name: str, actor: str = "codex") -> dict[str, Any]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("persistentvolumeclaims", "get")
        with audit_logger.span(
            "k8s.describe_pvc",
            {"k8s.namespace": self.namespace, "k8s.pvc": name},
        ):
            pvc = core_v1().read_namespaced_persistent_volume_claim(
                name=name,
                namespace=self.namespace,
            )
            result = api_client().sanitize_for_serialization(pvc)
            audit_logger.emit(
                action="get",
                resource="persistentvolumeclaims",
                namespace=self.namespace,
                name=name,
                status="success",
                actor=actor,
                tool="k8s_describe_pvc",
                response_summary={
                    "phase": getattr(pvc.status, "phase", None),
                    "volume_name": getattr(pvc.spec, "volume_name", None),
                },
            )
            return result

    def list_deployments(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("deployments", "list")
        items = apps_v1().list_namespaced_deployment(namespace=self.namespace).items
        result = [
            {
                "name": d.metadata.name,
                "replicas": d.spec.replicas,
                "ready_replicas": d.status.ready_replicas or 0,
                "available_replicas": d.status.available_replicas or 0,
                "updated_replicas": d.status.updated_replicas or 0,
                "images": [c.image for c in (d.spec.template.spec.containers or [])],
            }
            for d in items
        ]
        audit_logger.emit(action="list", resource="deployments", namespace=self.namespace, status="success", actor=actor, tool="k8s_list_deployments", response_summary={"count": len(result)})
        return result

    def list_statefulsets(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("statefulsets", "list")
        items = apps_v1().list_namespaced_stateful_set(namespace=self.namespace).items
        result = [
            {
                "name": s.metadata.name,
                "replicas": s.spec.replicas,
                "ready_replicas": s.status.ready_replicas or 0,
                "images": [c.image for c in (s.spec.template.spec.containers or [])],
            }
            for s in items
        ]
        audit_logger.emit(action="list", resource="statefulsets", namespace=self.namespace, status="success", actor=actor, tool="k8s_list_statefulsets", response_summary={"count": len(result)})
        return result

    def list_ingresses(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("ingresses", "list")
        items = networking_v1().list_namespaced_ingress(namespace=self.namespace).items
        result = []
        for ing in items:
            rules = []
            for r in ing.spec.rules or []:
                paths = []
                if r.http:
                    for p in r.http.paths or []:
                        paths.append({"path": p.path, "service": p.backend.service.name if p.backend.service else None, "port": p.backend.service.port.number if p.backend.service and p.backend.service.port else None})
                rules.append({"host": r.host, "paths": paths})
            result.append({"name": ing.metadata.name, "class": ing.spec.ingress_class_name, "rules": rules})
        audit_logger.emit(action="list", resource="ingresses", namespace=self.namespace, status="success", actor=actor, tool="k8s_list_ingresses", response_summary={"count": len(result)})
        return result

    def list_events(self, actor: str = "codex") -> list[dict[str, Any]]:
        policy.assert_namespace(self.namespace)
        policy.assert_resource_allowed("events", "list")
        items = core_v1().list_namespaced_event(namespace=self.namespace).items
        result = [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                "first_timestamp": str(e.first_timestamp),
                "last_timestamp": str(e.last_timestamp),
                "count": e.count,
            }
            for e in items
        ]
        audit_logger.emit(action="list", resource="events", namespace=self.namespace, status="success", actor=actor, tool="k8s_list_events", response_summary={"count": len(result)})
        return result

    def apply_manifest(self, manifest: dict[str, Any], dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None, tool: str = "k8s_apply_manifest") -> OperationResponse:
        try:
            kind, resource, name = policy.validate_manifest(manifest)
            namespace = manifest["metadata"]["namespace"]
            self._enforce_safe_defaults(manifest)
        except PolicyDeniedError as exc:
            metadata = manifest.get("metadata") or {}
            namespace = metadata.get("namespace") or "unknown"
            name = metadata.get("name")
            kind = manifest.get("kind") or "unknown"
            audit_logger.emit(
                action="apply",
                resource=str(kind),
                namespace=str(namespace),
                name=name,
                status="denied",
                actor=actor,
                request={"kind": kind, "dry_run": dry_run},
                correlation_id=correlation_id,
                tool=tool,
                resource_kind=str(kind),
                dry_run=dry_run,
                decision="denied",
                reason=str(exc),
            )
            raise
        audit_start = audit_logger.emit(action="apply", resource=resource, namespace=namespace, name=name, status="started", actor=actor, request={"kind": kind, "dry_run": dry_run}, correlation_id=correlation_id, tool=tool, resource_kind=kind, dry_run=dry_run, decision="allowed")
        with audit_logger.span("k8s.apply_manifest", {"k8s.namespace": namespace, "k8s.resource": resource, "k8s.name": name, "dry_run": dry_run}):
            try:
                dyn = DynamicClient(api_client())
                api = dyn.resources.get(api_version=manifest["apiVersion"], kind=kind)
                result = api.patch(
                    body=manifest,
                    namespace=namespace,
                    name=name,
                    content_type="application/apply-patch+yaml",
                    field_manager=config.policy.get("mutation_safety", {}).get("field_manager", "bosgenesis-k8s-inspector-mcp"),
                    force=True,
                    dry_run="All" if dry_run else None,
                )
                summary = {"kind": kind, "name": name, "resource_version": getattr(result.metadata, "resourceVersion", None)}
                audit_logger.emit(action="apply", resource=resource, namespace=namespace, name=name, status="success", actor=actor, response_summary=summary, correlation_id=audit_start["correlation_id"], tool=tool, resource_kind=kind, dry_run=dry_run, decision="allowed")
                return OperationResponse(status="success", namespace=namespace, resource=resource, name=name, dry_run=dry_run, summary=summary, audit_id=audit_start["audit_id"])
            except ApiException as exc:
                audit_logger.emit(action="apply", resource=resource, namespace=namespace, name=name, status="failed", actor=actor, error=str(exc), correlation_id=audit_start["correlation_id"], tool=tool, resource_kind=kind, dry_run=dry_run, decision="allowed", reason=str(exc))
                raise KubernetesOperationError(str(exc)) from exc

    def create_manifest(
        self,
        manifest: dict[str, Any],
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
        tool: str = "k8s_create_resource",
    ) -> OperationResponse:
        return self._manifest_mutation(
            action="create",
            manifest=manifest,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool=tool,
        )

    def update_manifest(
        self,
        manifest: dict[str, Any],
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
        tool: str = "k8s_update_resource",
    ) -> OperationResponse:
        return self._manifest_mutation(
            action="update",
            manifest=manifest,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool=tool,
        )

    def _manifest_mutation(
        self,
        action: str,
        manifest: dict[str, Any],
        dry_run: bool,
        actor: str,
        correlation_id: str | None,
        tool: str,
    ) -> OperationResponse:
        try:
            kind, resource, name = policy.validate_manifest_for_verb(manifest, action)
            namespace = manifest["metadata"]["namespace"]
            self._enforce_safe_defaults(manifest)
        except PolicyDeniedError as exc:
            metadata = manifest.get("metadata") or {}
            namespace = metadata.get("namespace") or "unknown"
            name = metadata.get("name")
            kind = manifest.get("kind") or "unknown"
            audit_logger.emit(
                action=action,
                resource=str(kind),
                namespace=str(namespace),
                name=name,
                status="denied",
                actor=actor,
                request={"kind": kind, "dry_run": dry_run},
                correlation_id=correlation_id,
                tool=tool,
                resource_kind=str(kind),
                dry_run=dry_run,
                decision="denied",
                reason=str(exc),
            )
            raise

        audit_start = audit_logger.emit(
            action=action,
            resource=resource,
            namespace=namespace,
            name=name,
            status="started",
            actor=actor,
            request={"kind": kind, "dry_run": dry_run},
            correlation_id=correlation_id,
            tool=tool,
            resource_kind=kind,
            dry_run=dry_run,
            decision="allowed",
        )
        with audit_logger.span(
            f"k8s.{action}_manifest",
            {"k8s.namespace": namespace, "k8s.resource": resource, "k8s.name": name, "dry_run": dry_run},
        ):
            try:
                dyn = DynamicClient(api_client())
                api = dyn.resources.get(api_version=manifest["apiVersion"], kind=kind)
                common = {"body": manifest, "namespace": namespace}
                if dry_run:
                    common["dry_run"] = "All"
                if action == "create":
                    result = api.create(**common)
                elif action == "update":
                    result = api.replace(name=name, **common)
                else:
                    raise PolicyDeniedError(f"Unsupported manifest mutation action '{action}'.")
                summary = {
                    "kind": kind,
                    "name": name,
                    "resource_version": getattr(result.metadata, "resourceVersion", None),
                }
                audit_logger.emit(
                    action=action,
                    resource=resource,
                    namespace=namespace,
                    name=name,
                    status="success",
                    actor=actor,
                    response_summary=summary,
                    correlation_id=audit_start["correlation_id"],
                    tool=tool,
                    resource_kind=kind,
                    dry_run=dry_run,
                    decision="allowed",
                )
                return OperationResponse(
                    status="success",
                    namespace=namespace,
                    resource=resource,
                    name=name,
                    dry_run=dry_run,
                    summary=summary,
                    audit_id=audit_start["audit_id"],
                )
            except ApiException as exc:
                audit_logger.emit(
                    action=action,
                    resource=resource,
                    namespace=namespace,
                    name=name,
                    status="failed",
                    actor=actor,
                    error=str(exc),
                    correlation_id=audit_start["correlation_id"],
                    tool=tool,
                    resource_kind=kind,
                    dry_run=dry_run,
                    decision="allowed",
                    reason=str(exc),
                )
                raise KubernetesOperationError(str(exc)) from exc

    def delete_resource(self, resource: str, name: str, namespace: str, dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None, tool: str = "k8s_delete_resource") -> OperationResponse:
        policy.assert_namespace(namespace)
        policy.assert_resource_allowed(resource, "delete")
        audit_start = audit_logger.emit(action="delete", resource=resource, namespace=namespace, name=name, status="started", actor=actor, request={"dry_run": dry_run}, correlation_id=correlation_id, tool=tool, dry_run=dry_run, decision="allowed")
        try:
            body = client.V1DeleteOptions()
            kwargs = {"name": name, "namespace": namespace, "body": body}
            if dry_run:
                kwargs["dry_run"] = "All"
            if resource == "pods":
                core_v1().delete_namespaced_pod(**kwargs)
            elif resource == "services":
                core_v1().delete_namespaced_service(**kwargs)
            elif resource == "configmaps":
                core_v1().delete_namespaced_config_map(**kwargs)
            elif resource == "persistentvolumeclaims":
                core_v1().delete_namespaced_persistent_volume_claim(**kwargs)
            elif resource == "deployments":
                apps_v1().delete_namespaced_deployment(**kwargs)
            elif resource == "statefulsets":
                apps_v1().delete_namespaced_stateful_set(**kwargs)
            elif resource == "daemonsets":
                apps_v1().delete_namespaced_daemon_set(**kwargs)
            elif resource == "jobs":
                batch_v1().delete_namespaced_job(**kwargs)
            elif resource == "cronjobs":
                batch_v1().delete_namespaced_cron_job(**kwargs)
            elif resource == "ingresses":
                networking_v1().delete_namespaced_ingress(**kwargs)
            else:
                raise PolicyDeniedError(f"Delete not implemented for '{resource}'.")
            audit_logger.emit(action="delete", resource=resource, namespace=namespace, name=name, status="success", actor=actor, correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed")
            return OperationResponse(status="success", namespace=namespace, resource=resource, name=name, dry_run=dry_run, audit_id=audit_start["audit_id"])
        except ApiException as exc:
            audit_logger.emit(action="delete", resource=resource, namespace=namespace, name=name, status="failed", actor=actor, error=str(exc), correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed", reason=str(exc))
            raise KubernetesOperationError(str(exc)) from exc

    def delete_collection(
        self,
        resource: str,
        namespace: str,
        label_selector: str | None = None,
        field_selector: str | None = None,
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
        tool: str = "k8s_delete_collection",
    ) -> OperationResponse:
        policy.assert_namespace(namespace)
        policy.assert_resource_allowed(resource, "deletecollection")
        if not label_selector and not field_selector:
            raise PolicyDeniedError("deletecollection requires a label_selector or field_selector.")

        api_version, kind = self._resource_def(resource)
        audit_start = audit_logger.emit(
            action="deletecollection",
            resource=resource,
            namespace=namespace,
            status="started",
            actor=actor,
            request={
                "dry_run": dry_run,
                "label_selector": label_selector,
                "field_selector": field_selector,
            },
            correlation_id=correlation_id,
            tool=tool,
            resource_kind=kind,
            dry_run=dry_run,
            decision="allowed",
        )
        try:
            dyn = DynamicClient(api_client())
            api = dyn.resources.get(api_version=api_version, kind=kind)
            kwargs: dict[str, Any] = {"namespace": namespace}
            if label_selector:
                kwargs["label_selector"] = label_selector
            if field_selector:
                kwargs["field_selector"] = field_selector
            if dry_run:
                kwargs["dry_run"] = "All"
            api.delete(**kwargs)
            summary = {"label_selector": label_selector, "field_selector": field_selector}
            audit_logger.emit(
                action="deletecollection",
                resource=resource,
                namespace=namespace,
                status="success",
                actor=actor,
                response_summary=summary,
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind=kind,
                dry_run=dry_run,
                decision="allowed",
            )
            return OperationResponse(
                status="success",
                namespace=namespace,
                resource=resource,
                dry_run=dry_run,
                summary=summary,
                audit_id=audit_start["audit_id"],
            )
        except ApiException as exc:
            audit_logger.emit(
                action="deletecollection",
                resource=resource,
                namespace=namespace,
                status="failed",
                actor=actor,
                error=str(exc),
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind=kind,
                dry_run=dry_run,
                decision="allowed",
                reason=str(exc),
            )
            raise KubernetesOperationError(str(exc)) from exc

    def patch_resource(self, resource: str, name: str, namespace: str, patch: dict[str, Any], dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None, tool: str = "k8s_patch_resource") -> OperationResponse:
        policy.assert_namespace(namespace)
        policy.assert_resource_allowed(resource, "patch")
        policy.validate_patch_payload(patch)
        api_version, kind = self._resource_def(resource)
        audit_start = audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="started", actor=actor, request={"dry_run": dry_run, "patch_keys": list(patch.keys())}, correlation_id=correlation_id, tool=tool, dry_run=dry_run, decision="allowed")
        kwargs = {"name": name, "namespace": namespace, "body": patch}
        if dry_run:
            kwargs["dry_run"] = "All"
        try:
            dyn = DynamicClient(api_client())
            api = dyn.resources.get(api_version=api_version, kind=kind)
            api.patch(**kwargs)
            audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="success", actor=actor, correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed")
            return OperationResponse(status="success", namespace=namespace, resource=resource, name=name, dry_run=dry_run, audit_id=audit_start["audit_id"])
        except ApiException as exc:
            audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="failed", actor=actor, error=str(exc), correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed", reason=str(exc))
            raise KubernetesOperationError(str(exc)) from exc

    def bind_pod(
        self,
        pod_name: str,
        node_name: str,
        namespace: str,
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
        tool: str = "k8s_bind_pod",
    ) -> OperationResponse:
        policy.assert_namespace(namespace)
        policy.assert_resource_allowed("pods", "bind")
        audit_start = audit_logger.emit(
            action="bind",
            resource="pods/binding",
            namespace=namespace,
            name=pod_name,
            status="started",
            actor=actor,
            request={"dry_run": dry_run, "target_kind": "Node"},
            correlation_id=correlation_id,
            tool=tool,
            resource_kind="Binding",
            dry_run=dry_run,
            decision="allowed",
        )
        try:
            body = client.V1Binding(
                metadata=client.V1ObjectMeta(name=pod_name, namespace=namespace),
                target=client.V1ObjectReference(api_version="v1", kind="Node", name=node_name),
            )
            kwargs: dict[str, Any] = {"namespace": namespace, "body": body}
            if dry_run:
                kwargs["dry_run"] = "All"
            core_v1().create_namespaced_binding(**kwargs)
            summary = {"pod": pod_name, "target_kind": "Node", "target_name": node_name}
            audit_logger.emit(
                action="bind",
                resource="pods/binding",
                namespace=namespace,
                name=pod_name,
                status="success",
                actor=actor,
                response_summary=summary,
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Binding",
                dry_run=dry_run,
                decision="allowed",
            )
            return OperationResponse(
                status="success",
                namespace=namespace,
                resource="pods/binding",
                name=pod_name,
                dry_run=dry_run,
                summary=summary,
                audit_id=audit_start["audit_id"],
            )
        except ApiException as exc:
            audit_logger.emit(
                action="bind",
                resource="pods/binding",
                namespace=namespace,
                name=pod_name,
                status="failed",
                actor=actor,
                error=str(exc),
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Binding",
                dry_run=dry_run,
                decision="allowed",
                reason=str(exc),
            )
            raise KubernetesOperationError(str(exc)) from exc

    def scale_deployment(self, name: str, replicas: int, namespace: str, dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None) -> OperationResponse:
        patch = {"spec": {"replicas": replicas}}
        return self.patch_resource("deployments", name, namespace, patch, dry_run, actor, correlation_id, tool="k8s_scale_deployment")

    def create_ephemeral_secret(
        self,
        name: str,
        string_data: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        secret_type: str = "Opaque",
        namespace: str | None = None,
        ttl_seconds: int = 3600,
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
        tool: str = "k8s_create_ephemeral_secret",
    ) -> OperationResponse:
        self._prune_expired_secret_sessions()
        namespace = policy.assert_namespace(namespace or self.namespace)
        secret_name = self._assert_ephemeral_secret_name(name)
        if not string_data and not data:
            raise PolicyDeniedError("Ephemeral Secret creation requires string_data or data.")
        if ttl_seconds < 60 or ttl_seconds > 86400:
            raise PolicyDeniedError("Ephemeral Secret ttl_seconds must be between 60 and 86400.")

        correlation_id = correlation_id or str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        key_names = sorted(set((string_data or {}).keys()) | set((data or {}).keys()))
        metadata = client.V1ObjectMeta(
            name=secret_name,
            namespace=namespace,
            labels={
                SECRET_MANAGED_BY_LABEL: SECRET_MANAGED_BY,
                SECRET_OWNER_LABEL: "mcp-session",
            },
            annotations={
                SECRET_CORRELATION_ANNOTATION: correlation_id,
                SECRET_EXPIRES_AT_ANNOTATION: expires_at.isoformat(),
            },
        )
        body = client.V1Secret(
            metadata=metadata,
            type=secret_type,
            string_data=string_data or None,
            data=data or None,
        )
        audit_start = audit_logger.emit(
            action="create",
            resource="secrets",
            namespace=namespace,
            name=secret_name,
            status="started",
            actor=actor,
            request={
                "kind": "Secret",
                "dry_run": dry_run,
                "key_names": key_names,
                "ttl_seconds": ttl_seconds,
            },
            correlation_id=correlation_id,
            tool=tool,
            resource_kind="Secret",
            dry_run=dry_run,
            decision="allowed",
        )
        try:
            kwargs: dict[str, Any] = {"namespace": namespace, "body": body}
            if dry_run:
                kwargs["dry_run"] = "All"
            core_v1().create_namespaced_secret(**kwargs)
            if not dry_run:
                _owned_secret_sessions[correlation_id] = {
                    "name": secret_name,
                    "namespace": namespace,
                    "expires_at": expires_at,
                    "key_names": key_names,
                }
            summary = {
                "kind": "Secret",
                "name": secret_name,
                "key_names": key_names,
                "ttl_seconds": ttl_seconds,
                "expires_at": expires_at.isoformat(),
                "correlation_id": correlation_id,
                "values_returned": False,
            }
            audit_logger.emit(
                action="create",
                resource="secrets",
                namespace=namespace,
                name=secret_name,
                status="success",
                actor=actor,
                response_summary=summary,
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Secret",
                dry_run=dry_run,
                decision="allowed",
            )
            return OperationResponse(
                status="success",
                namespace=namespace,
                resource="secrets",
                name=secret_name,
                dry_run=dry_run,
                summary=summary,
                audit_id=audit_start["audit_id"],
            )
        except ApiException as exc:
            audit_logger.emit(
                action="create",
                resource="secrets",
                namespace=namespace,
                name=secret_name,
                status="failed",
                actor=actor,
                error=str(exc),
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Secret",
                dry_run=dry_run,
                decision="allowed",
                reason=str(exc),
            )
            raise KubernetesOperationError(str(exc)) from exc

    def delete_ephemeral_secret(
        self,
        name: str,
        correlation_id: str,
        namespace: str | None = None,
        dry_run: bool = False,
        actor: str = "codex",
        tool: str = "k8s_delete_ephemeral_secret",
    ) -> OperationResponse:
        self._prune_expired_secret_sessions()
        namespace = policy.assert_namespace(namespace or self.namespace)
        secret_name = self._assert_ephemeral_secret_name(name)
        record = _owned_secret_sessions.get(correlation_id)
        if not record or record.get("name") != secret_name or record.get("namespace") != namespace:
            raise PolicyDeniedError(
                "Ephemeral Secret deletion requires the matching in-session correlation_id."
            )

        audit_start = audit_logger.emit(
            action="delete",
            resource="secrets",
            namespace=namespace,
            name=secret_name,
            status="started",
            actor=actor,
            request={"dry_run": dry_run},
            correlation_id=correlation_id,
            tool=tool,
            resource_kind="Secret",
            dry_run=dry_run,
            decision="allowed",
        )
        try:
            kwargs: dict[str, Any] = {
                "name": secret_name,
                "namespace": namespace,
                "body": client.V1DeleteOptions(),
            }
            if dry_run:
                kwargs["dry_run"] = "All"
            core_v1().delete_namespaced_secret(**kwargs)
            if not dry_run:
                _owned_secret_sessions.pop(correlation_id, None)
            summary = {
                "kind": "Secret",
                "name": secret_name,
                "correlation_id": correlation_id,
                "values_returned": False,
            }
            audit_logger.emit(
                action="delete",
                resource="secrets",
                namespace=namespace,
                name=secret_name,
                status="success",
                actor=actor,
                response_summary=summary,
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Secret",
                dry_run=dry_run,
                decision="allowed",
            )
            return OperationResponse(
                status="success",
                namespace=namespace,
                resource="secrets",
                name=secret_name,
                dry_run=dry_run,
                summary=summary,
                audit_id=audit_start["audit_id"],
            )
        except ApiException as exc:
            audit_logger.emit(
                action="delete",
                resource="secrets",
                namespace=namespace,
                name=secret_name,
                status="failed",
                actor=actor,
                error=str(exc),
                correlation_id=audit_start["correlation_id"],
                tool=tool,
                resource_kind="Secret",
                dry_run=dry_run,
                decision="allowed",
                reason=str(exc),
            )
            raise KubernetesOperationError(str(exc)) from exc

    def create_pvc(
        self,
        manifest: dict[str, Any],
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
    ) -> OperationResponse:
        self._assert_pvc_manifest(manifest)
        return self.create_manifest(
            manifest=manifest,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool="k8s_create_pvc",
        )

    def update_pvc(
        self,
        manifest: dict[str, Any],
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
    ) -> OperationResponse:
        self._assert_pvc_manifest(manifest)
        return self.update_manifest(
            manifest=manifest,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool="k8s_update_pvc",
        )

    def patch_pvc(
        self,
        name: str,
        patch: dict[str, Any],
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
    ) -> OperationResponse:
        return self.patch_resource(
            resource="persistentvolumeclaims",
            name=name,
            namespace=self.namespace,
            patch=patch,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool="k8s_patch_pvc",
        )

    def delete_pvc(
        self,
        name: str,
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
    ) -> OperationResponse:
        return self.delete_resource(
            resource="persistentvolumeclaims",
            name=name,
            namespace=self.namespace,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool="k8s_delete_pvc",
        )

    def delete_pvc_collection(
        self,
        label_selector: str | None = None,
        field_selector: str | None = None,
        dry_run: bool = False,
        actor: str = "codex",
        correlation_id: str | None = None,
    ) -> OperationResponse:
        return self.delete_collection(
            resource="persistentvolumeclaims",
            namespace=self.namespace,
            label_selector=label_selector,
            field_selector=field_selector,
            dry_run=dry_run,
            actor=actor,
            correlation_id=correlation_id,
            tool="k8s_delete_pvc_collection",
        )

    def apply_yaml_text(self, yaml_text: str, dry_run: bool = False, actor: str = "codex") -> list[dict[str, Any]]:
        docs = [doc for doc in yaml.safe_load_all(yaml_text) if doc]
        return [self.apply_manifest(doc, dry_run=dry_run, actor=actor).model_dump() for doc in docs]

    @staticmethod
    def _resource_def(resource: str) -> tuple[str, str]:
        try:
            return RESOURCE_DEFS[resource]
        except KeyError as exc:
            raise PolicyDeniedError(f"Resource '{resource}' is not supported by this MCP server.") from exc

    @staticmethod
    def _enforce_safe_defaults(manifest: dict[str, Any]) -> None:
        kind = manifest.get("kind")
        specs = []
        if kind == "Pod":
            specs.append(manifest.setdefault("spec", {}))
        elif kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
            specs.append(manifest.setdefault("spec", {}).setdefault("template", {}).setdefault("spec", {}))
        elif kind == "CronJob":
            specs.append(manifest.setdefault("spec", {}).setdefault("jobTemplate", {}).setdefault("spec", {}).setdefault("template", {}).setdefault("spec", {}))
        for spec in specs:
            spec.setdefault("automountServiceAccountToken", False)

    @staticmethod
    def _assert_pvc_manifest(manifest: dict[str, Any]) -> None:
        if manifest.get("kind") != "PersistentVolumeClaim":
            raise PolicyDeniedError("PVC-specific operations require kind 'PersistentVolumeClaim'.")

    @staticmethod
    def _assert_ephemeral_secret_name(name: str) -> str:
        if not name or not name.startswith(SECRET_NAME_PREFIX):
            raise PolicyDeniedError(
                f"Ephemeral Secret names must start with '{SECRET_NAME_PREFIX}'."
            )
        return name

    @staticmethod
    def _prune_expired_secret_sessions() -> None:
        now = datetime.now(timezone.utc)
        expired = [
            correlation_id
            for correlation_id, record in _owned_secret_sessions.items()
            if record.get("expires_at") and record["expires_at"] <= now
        ]
        for correlation_id in expired:
            _owned_secret_sessions.pop(correlation_id, None)

    @staticmethod
    def _pod_summary(pod: Any) -> dict[str, Any]:
        ready = 0
        total = len(pod.status.container_statuses or [])
        restarts = 0
        for cs in pod.status.container_statuses or []:
            if cs.ready:
                ready += 1
            restarts += cs.restart_count or 0
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "ready": f"{ready}/{total}",
            "restarts": restarts,
            "node": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "start_time": str(pod.status.start_time) if pod.status.start_time else None,
            "images": [c.image for c in pod.spec.containers or []],
        }

    @staticmethod
    def _pvc_summary(pvc: Any) -> dict[str, Any]:
        requested = None
        capacity = None
        if pvc.spec and pvc.spec.resources and pvc.spec.resources.requests:
            requested = pvc.spec.resources.requests.get("storage")
        if pvc.status and pvc.status.capacity:
            capacity = pvc.status.capacity.get("storage")
        return {
            "name": pvc.metadata.name,
            "namespace": pvc.metadata.namespace,
            "phase": pvc.status.phase if pvc.status else None,
            "storage_class": pvc.spec.storage_class_name if pvc.spec else None,
            "volume_name": pvc.spec.volume_name if pvc.spec else None,
            "access_modes": pvc.spec.access_modes or [] if pvc.spec else [],
            "requested_storage": requested,
            "capacity": capacity,
            "volume_mode": pvc.spec.volume_mode if pvc.spec else None,
            "created_at": str(pvc.metadata.creation_timestamp) if pvc.metadata.creation_timestamp else None,
        }

    @staticmethod
    def _configmap_summary(configmap: Any) -> dict[str, Any]:
        data = configmap.data or {}
        binary_data = configmap.binary_data or {}
        return {
            "name": configmap.metadata.name,
            "namespace": configmap.metadata.namespace,
            "data_keys": sorted(data.keys()),
            "binary_data_keys": sorted(binary_data.keys()),
            "data_key_count": len(data),
            "binary_data_key_count": len(binary_data),
            "labels": configmap.metadata.labels or {},
            "annotations": configmap.metadata.annotations or {},
            "created_at": str(configmap.metadata.creation_timestamp) if configmap.metadata.creation_timestamp else None,
        }


ops = KubernetesOperations()
