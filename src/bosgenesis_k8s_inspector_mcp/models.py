from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApplyManifestRequest(BaseModel):
    manifest: dict[str, Any]
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class DeleteResourceRequest(BaseModel):
    resource: Literal[
        "pods",
        "services",
        "configmaps",
        "persistentvolumeclaims",
        "deployments",
        "statefulsets",
        "daemonsets",
        "jobs",
        "cronjobs",
        "ingresses",
    ]
    name: str
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class PatchResourceRequest(BaseModel):
    resource: Literal[
        "pods",
        "services",
        "configmaps",
        "persistentvolumeclaims",
        "deployments",
        "statefulsets",
        "daemonsets",
        "jobs",
        "cronjobs",
        "ingresses",
    ]
    name: str
    patch: dict[str, Any]
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class ScaleDeploymentRequest(BaseModel):
    name: str
    replicas: int = Field(ge=0, le=20)
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class OperationResponse(BaseModel):
    status: str
    namespace: str
    resource: str
    name: str | None = None
    dry_run: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)
    audit_id: str | None = None
