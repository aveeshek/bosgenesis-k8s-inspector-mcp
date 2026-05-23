from __future__ import annotations

from contextlib import asynccontextmanager
from secrets import compare_digest

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .config import config
from .errors import KubernetesOperationError, PolicyDeniedError
from .k8s_client import auth_diagnostics
from .models import (
    ApplyManifestRequest,
    BindPodRequest,
    DeleteCollectionRequest,
    DeleteResourceRequest,
    ManifestMutationRequest,
    PatchResourceRequest,
    PvcDeleteCollectionRequest,
    PvcPatchRequest,
    ScaleDeploymentRequest,
)
from .operations import ops
from .server_mcp import mcp as mcp_server
from .server_mcp import streamable_http_app
from .telemetry import setup_telemetry

setup_telemetry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="BOS Genesis Kubernetes Inspector MCP API",
    version="0.1.0",
    description="Namespace-scoped Kubernetes inspector/operator API for BOS Genesis.",
    lifespan=lifespan,
)
FastAPIInstrumentor.instrument_app(app)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not config.require_api_key:
        return
    expected = config.env.api_key
    if not expected or expected == "change-me-later":
        # Allow local bootstrap, but force users to set a real key before serious use.
        return
    if not x_api_key or not compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def require_mutation_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not config.require_api_key:
        return
    expected = config.env.api_key
    if not expected or expected == "change-me-later":
        raise HTTPException(
            status_code=503,
            detail="Mutating endpoints require a non-placeholder BOSGENESIS_API_KEY.",
        )
    if not x_api_key or not compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PolicyDeniedError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, KubernetesOperationError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "bosgenesis-k8s-inspector-mcp",
        "namespace": config.namespace,
        "mode": "api",
        "k8s_auth_mode": config.k8s_auth_mode,
        "k8s_auth": auth_diagnostics(),
        "mcp_endpoint": "/mcp",
        "otel_enabled": config.env.otel_enabled,
    }


@app.get("/namespace/summary", dependencies=[Depends(require_api_key)])
def namespace_summary(actor: str = Query(default="codex")) -> dict:
    try:
        return ops.namespace_summary(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/pods", dependencies=[Depends(require_api_key)])
def list_pods(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_pods(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/pods/{pod_name}", dependencies=[Depends(require_api_key)])
def describe_pod(pod_name: str, actor: str = Query(default="codex")) -> dict:
    try:
        return ops.describe_pod(pod_name, actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/pods/{pod_name}/logs", dependencies=[Depends(require_api_key)])
def pod_logs(pod_name: str, tail_lines: int = Query(default=200, ge=1, le=1000), actor: str = Query(default="codex")) -> dict:
    try:
        return ops.pod_logs(pod_name, tail_lines=tail_lines, actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/services", dependencies=[Depends(require_api_key)])
def list_services(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_services(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/pvcs", dependencies=[Depends(require_api_key)])
def list_pvcs(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_pvcs(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/pvcs/{pvc_name}", dependencies=[Depends(require_api_key)])
def describe_pvc(pvc_name: str, actor: str = Query(default="codex")) -> dict:
    try:
        return ops.describe_pvc(pvc_name, actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/deployments", dependencies=[Depends(require_api_key)])
def list_deployments(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_deployments(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/statefulsets", dependencies=[Depends(require_api_key)])
def list_statefulsets(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_statefulsets(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/ingresses", dependencies=[Depends(require_api_key)])
def list_ingresses(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_ingresses(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.get("/events", dependencies=[Depends(require_api_key)])
def list_events(actor: str = Query(default="codex")) -> list[dict]:
    try:
        return ops.list_events(actor=actor)
    except Exception as exc:
        raise handle_error(exc)


@app.post("/apply", dependencies=[Depends(require_mutation_api_key)])
def apply_manifest(req: ApplyManifestRequest) -> dict:
    try:
        return ops.apply_manifest(
            manifest=req.manifest,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/create", dependencies=[Depends(require_mutation_api_key)])
def create_resource(req: ManifestMutationRequest) -> dict:
    try:
        return ops.create_manifest(
            manifest=req.manifest,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/update", dependencies=[Depends(require_mutation_api_key)])
def update_resource(req: ManifestMutationRequest) -> dict:
    try:
        return ops.update_manifest(
            manifest=req.manifest,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/pvcs", dependencies=[Depends(require_mutation_api_key)])
def create_pvc(req: ManifestMutationRequest) -> dict:
    try:
        return ops.create_pvc(
            manifest=req.manifest,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.put("/pvcs/{pvc_name}", dependencies=[Depends(require_mutation_api_key)])
def update_pvc(pvc_name: str, req: ManifestMutationRequest) -> dict:
    try:
        if req.manifest.get("metadata", {}).get("name") != pvc_name:
            raise PolicyDeniedError("PVC manifest metadata.name must match the URL pvc_name.")
        return ops.update_pvc(
            manifest=req.manifest,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/delete", dependencies=[Depends(require_mutation_api_key)])
def delete_resource(req: DeleteResourceRequest) -> dict:
    try:
        return ops.delete_resource(
            resource=req.resource,
            name=req.name,
            namespace=req.namespace,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.delete("/pvcs/{pvc_name}", dependencies=[Depends(require_mutation_api_key)])
def delete_pvc(
    pvc_name: str,
    dry_run: bool = Query(default=False),
    actor: str = Query(default="codex"),
) -> dict:
    try:
        return ops.delete_pvc(
            name=pvc_name,
            dry_run=dry_run,
            actor=actor,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/deletecollection", dependencies=[Depends(require_mutation_api_key)])
def delete_collection(req: DeleteCollectionRequest) -> dict:
    try:
        return ops.delete_collection(
            resource=req.resource,
            namespace=req.namespace,
            label_selector=req.label_selector,
            field_selector=req.field_selector,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/pvcs/deletecollection", dependencies=[Depends(require_mutation_api_key)])
def delete_pvc_collection(req: PvcDeleteCollectionRequest) -> dict:
    try:
        return ops.delete_pvc_collection(
            label_selector=req.label_selector,
            field_selector=req.field_selector,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/patch", dependencies=[Depends(require_mutation_api_key)])
def patch_resource(req: PatchResourceRequest) -> dict:
    try:
        return ops.patch_resource(
            resource=req.resource,
            name=req.name,
            namespace=req.namespace,
            patch=req.patch,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.patch("/pvcs/{pvc_name}", dependencies=[Depends(require_mutation_api_key)])
def patch_pvc(pvc_name: str, req: PvcPatchRequest) -> dict:
    try:
        return ops.patch_pvc(
            name=pvc_name,
            patch=req.patch,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/bind", dependencies=[Depends(require_mutation_api_key)])
def bind_pod(req: BindPodRequest) -> dict:
    try:
        return ops.bind_pod(
            pod_name=req.pod_name,
            node_name=req.node_name,
            namespace=req.namespace,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


@app.post("/scale/deployment", dependencies=[Depends(require_mutation_api_key)])
def scale_deployment(req: ScaleDeploymentRequest) -> dict:
    try:
        return ops.scale_deployment(
            name=req.name,
            replicas=req.replicas,
            namespace=req.namespace,
            dry_run=req.dry_run,
            actor=req.actor,
            correlation_id=req.correlation_id,
        ).model_dump()
    except Exception as exc:
        raise handle_error(exc)


app.mount("/", streamable_http_app(), name="mcp")


def run() -> None:
    uvicorn.run(app, host=config.env.api_host, port=config.env.api_port)


if __name__ == "__main__":
    run()
