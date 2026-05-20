from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pythonjsonlogger import jsonlogger
from opentelemetry import trace

from .config import config
from .telemetry import get_tracer

logger = logging.getLogger("bosgenesis.audit")
handler = logging.StreamHandler()
handler.setFormatter(
    jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(audit_event)s")
)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resource_kind_from_resource(resource: str) -> str:
    mapping = {
        "configmaps": "ConfigMap",
        "cronjobs": "CronJob",
        "daemonsets": "DaemonSet",
        "deployments": "Deployment",
        "events": "Event",
        "ingresses": "Ingress",
        "jobs": "Job",
        "namespace": "Namespace",
        "persistentvolumeclaims": "PersistentVolumeClaim",
        "pods": "Pod",
        "pods/log": "PodLog",
        "replicasets": "ReplicaSet",
        "services": "Service",
        "statefulsets": "StatefulSet",
    }
    return mapping.get(resource.lower(), resource)


class AuditLogger:
    def __init__(self) -> None:
        self.file_path = Path(config.env.audit_log_file)
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # File logging should never block Kubernetes operations.
            pass

    def emit(
        self,
        *,
        action: str,
        resource: str,
        namespace: str,
        name: str | None = None,
        status: str = "started",
        actor: str | None = None,
        request: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
        error: str | None = None,
        correlation_id: str | None = None,
        tool: str | None = None,
        operation: str | None = None,
        resource_kind: str | None = None,
        resource_name: str | None = None,
        dry_run: bool | None = None,
        decision: str = "allowed",
        reason: str | None = None,
    ) -> dict[str, Any]:
        request = request or {}
        response_summary = response_summary or {}
        operation = operation or action
        resource_name = resource_name if resource_name is not None else name
        resource_kind = resource_kind or request.get("kind") or response_summary.get("kind") or resource_kind_from_resource(resource)
        if dry_run is None:
            dry_run = request.get("dry_run")
        reason = reason if reason is not None else error
        event = {
            "audit_id": str(uuid4()),
            "timestamp": now_iso(),
            "actor": actor or "unknown",
            "tool": tool,
            "operation": operation,
            "namespace": namespace,
            "resource_kind": resource_kind,
            "resource_name": resource_name,
            "dry_run": dry_run,
            "decision": decision,
            "status": status,
            "reason": reason,
            "correlation_id": correlation_id or str(uuid4()),
            # Backward-compatible fields consumed by existing logs/tests.
            "action": action,
            "resource": resource,
            "name": name,
            "request": request,
            "response_summary": response_summary,
            "error": error,
        }
        logger.info("k8s_inspector_audit", extra={"audit_event": event})
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event("k8s_inspector_audit", attributes=_otel_attrs(event))
        try:
            with self.file_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as exc:
            logger.warning("audit_file_write_failed", extra={"audit_event": {"error": str(exc)}})
        return event

    def span(self, name: str, attrs: dict[str, Any] | None = None):
        tracer = get_tracer()
        return tracer.start_as_current_span(name, attributes=attrs or {})


audit_logger = AuditLogger()


def _otel_attrs(event: dict[str, Any]) -> dict[str, str | bool | int | float]:
    attrs: dict[str, str | bool | int | float] = {}
    for key in (
        "audit_id",
        "timestamp",
        "actor",
        "tool",
        "operation",
        "namespace",
        "resource_kind",
        "resource_name",
        "dry_run",
        "decision",
        "status",
        "reason",
        "correlation_id",
    ):
        value = event.get(key)
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            attrs[f"audit.{key}"] = value
        else:
            attrs[f"audit.{key}"] = str(value)
    return attrs
