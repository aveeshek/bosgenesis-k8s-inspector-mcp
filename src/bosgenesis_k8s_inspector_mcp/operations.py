from __future__ import annotations

from typing import Any

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
            summary = {
                "namespace": namespace,
                "counts": {
                    "pods": len(pods),
                    "services": len(services),
                    "deployments": len(deployments),
                    "ingresses": len(ingresses),
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

    def patch_resource(self, resource: str, name: str, namespace: str, patch: dict[str, Any], dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None, tool: str = "k8s_patch_resource") -> OperationResponse:
        policy.assert_namespace(namespace)
        policy.assert_resource_allowed(resource, "patch")
        audit_start = audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="started", actor=actor, request={"dry_run": dry_run, "patch_keys": list(patch.keys())}, correlation_id=correlation_id, tool=tool, dry_run=dry_run, decision="allowed")
        kwargs = {"name": name, "namespace": namespace, "body": patch}
        if dry_run:
            kwargs["dry_run"] = "All"
        try:
            if resource == "deployments":
                apps_v1().patch_namespaced_deployment(**kwargs)
            elif resource == "statefulsets":
                apps_v1().patch_namespaced_stateful_set(**kwargs)
            elif resource == "daemonsets":
                apps_v1().patch_namespaced_daemon_set(**kwargs)
            elif resource == "services":
                core_v1().patch_namespaced_service(**kwargs)
            elif resource == "configmaps":
                core_v1().patch_namespaced_config_map(**kwargs)
            elif resource == "ingresses":
                networking_v1().patch_namespaced_ingress(**kwargs)
            elif resource == "pods":
                core_v1().patch_namespaced_pod(**kwargs)
            elif resource == "jobs":
                batch_v1().patch_namespaced_job(**kwargs)
            elif resource == "cronjobs":
                batch_v1().patch_namespaced_cron_job(**kwargs)
            else:
                raise PolicyDeniedError(f"Patch not implemented for '{resource}'.")
            audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="success", actor=actor, correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed")
            return OperationResponse(status="success", namespace=namespace, resource=resource, name=name, dry_run=dry_run, audit_id=audit_start["audit_id"])
        except ApiException as exc:
            audit_logger.emit(action="patch", resource=resource, namespace=namespace, name=name, status="failed", actor=actor, error=str(exc), correlation_id=audit_start["correlation_id"], tool=tool, dry_run=dry_run, decision="allowed", reason=str(exc))
            raise KubernetesOperationError(str(exc)) from exc

    def scale_deployment(self, name: str, replicas: int, namespace: str, dry_run: bool = False, actor: str = "codex", correlation_id: str | None = None) -> OperationResponse:
        patch = {"spec": {"replicas": replicas}}
        return self.patch_resource("deployments", name, namespace, patch, dry_run, actor, correlation_id, tool="k8s_scale_deployment")

    def apply_yaml_text(self, yaml_text: str, dry_run: bool = False, actor: str = "codex") -> list[dict[str, Any]]:
        docs = [doc for doc in yaml.safe_load_all(yaml_text) if doc]
        return [self.apply_manifest(doc, dry_run=dry_run, actor=actor).model_dump() for doc in docs]

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


ops = KubernetesOperations()
