from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WritableResource = Literal[
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


class ApplyManifestRequest(BaseModel):
    manifest: dict[str, Any]
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class ManifestMutationRequest(ApplyManifestRequest):
    pass


class DeleteResourceRequest(BaseModel):
    resource: WritableResource
    name: str
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class DeleteCollectionRequest(BaseModel):
    resource: WritableResource
    namespace: str = Field(default="bosgenesis")
    label_selector: str | None = None
    field_selector: str | None = None
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class PvcDeleteCollectionRequest(BaseModel):
    label_selector: str | None = None
    field_selector: str | None = None
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class PatchResourceRequest(BaseModel):
    resource: WritableResource
    name: str
    patch: dict[str, Any]
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class PvcPatchRequest(BaseModel):
    patch: dict[str, Any]
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class BindPodRequest(BaseModel):
    pod_name: str
    node_name: str
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


class EphemeralSecretCreateRequest(BaseModel):
    name: str
    string_data: dict[str, str] = Field(default_factory=dict)
    data: dict[str, str] = Field(default_factory=dict)
    secret_type: str = "Opaque"
    namespace: str = Field(default="bosgenesis")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    dry_run: bool = False
    actor: str = "codex"
    correlation_id: str | None = None


class EphemeralSecretDeleteRequest(BaseModel):
    name: str
    correlation_id: str
    namespace: str = Field(default="bosgenesis")
    dry_run: bool = False
    actor: str = "codex"


class OperationResponse(BaseModel):
    status: str
    namespace: str
    resource: str
    name: str | None = None
    dry_run: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)
    audit_id: str | None = None
