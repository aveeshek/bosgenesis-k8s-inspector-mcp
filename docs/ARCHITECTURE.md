# Architecture

```mermaid
flowchart LR
    Codex[Codex / AI Agent] --> MCP[BOS Genesis K8s Inspector MCP]
    UI[BOS AI Studio / curl / n8n] --> API[REST API]
    MCP --> CORE[Policy + Operation Layer]
    API --> CORE
    CORE --> AUDIT[Audit Logger]
    CORE --> OTEL[OpenTelemetry]
    CORE --> K8S[Kubernetes Python Client]
    K8S --> RBAC[ServiceAccount + RoleBinding]
    RBAC --> NS[(bosgenesis namespace only)]
    OTEL --> SIGNOZ[SigNoz OTel Collector]
```

## Security boundary

```mermaid
flowchart TB
    Request[Incoming request] --> CheckNS{Namespace == bosgenesis?}
    CheckNS -- No --> Deny1[Reject + Audit]
    CheckNS -- Yes --> CheckRes{Resource allowed?}
    CheckRes -- No --> Deny2[Reject + Audit]
    CheckRes -- Yes --> CheckKind{Cluster-scoped or blocked kind?}
    CheckKind -- Yes --> Deny3[Reject + Audit]
    CheckKind -- No --> CheckPod{Unsafe pod spec?}
    CheckPod -- Yes --> Deny4[Reject + Audit]
    CheckPod -- No --> Execute[Call Kubernetes API]
    Execute --> Audit[Audit success/failure]
```

## Audit flow

```mermaid
sequenceDiagram
    participant C as Codex
    participant M as MCP/API
    participant P as Policy Engine
    participant K as Kubernetes API
    participant A as Audit JSONL
    participant S as SigNoz

    C->>M: list/get/apply/patch/delete request
    M->>P: validate namespace, resource, safety
    P-->>M: allow or deny
    M->>A: write started/denied event
    alt allowed
      M->>K: Kubernetes API call using namespace Role
      K-->>M: result
      M->>A: write success/failure event
      M->>S: emit OpenTelemetry span
      M-->>C: normalized response
    else denied
      M->>S: emit denied span
      M-->>C: policy denied response
    end
```

## ConfigMap read boundary

ConfigMaps are allowed namespaced application configuration resources, but they can still contain sensitive values when applications misuse them. The direct ConfigMap read surface is therefore intentionally split:

- `k8s_list_configmaps` and `GET /configmaps` return names, labels, annotations, and key names only.
- `k8s_get_configmap` and `GET /configmaps/{configmap_name}` return key names by default.
- ConfigMap values are returned only when the caller explicitly sets `include_data=true`.

This does not change the hard Secret read guardrail. Kubernetes Secrets remain blocked for generic operations, and RBAC grants only create/delete for the dedicated ephemeral Secret workflow.

## Ephemeral Secret boundary

The MCP server has a narrow write-only Secret exception for installation workflows that need Kubernetes Secret references.

```mermaid
flowchart TB
    Start["Create ephemeral Secret request"] --> Auth["Mutation API key"]
    Auth --> Name["Require name prefix bosgenesis-mcp-"]
    Name --> Metadata["Add MCP labels, correlation ID, and expires-at annotation"]
    Metadata --> Create["Create namespaced Secret"]
    Create --> Response["Return name, key names, TTL, correlation ID"]
    Response --> NoValues["Never return Secret values"]

    Delete["Delete ephemeral Secret request"] --> Match["Match in-session correlation ID"]
    Match --> DeleteCall["Delete namespaced Secret by name"]
```

There are still no Secret read, list, describe, update, patch, or generic apply paths. The Kubernetes Role grants `create` and `delete` for Secrets only, not `get`, `list`, `watch`, `update`, or `patch`.
