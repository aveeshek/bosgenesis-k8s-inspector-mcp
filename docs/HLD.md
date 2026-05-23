# BOS Genesis Kubernetes Inspector MCP - High Level Design

## Purpose

`bosgenesis-k8s-inspector-mcp` is a namespace-scoped Kubernetes operations service for the BOS Genesis platform.

It exposes:

- A remote Streamable HTTP MCP endpoint at `/mcp`
- A REST API for direct integrations and diagnostics
- A governed Kubernetes operation layer restricted to the `bosgenesis` namespace

The service runs inside Kubernetes and uses in-cluster authentication through its own ServiceAccount and namespace RoleBinding.

## Goals

- Let Codex and other MCP clients inspect BOS Genesis Kubernetes resources without local kubeconfig access.
- Allow controlled mutations for approved namespaced resources.
- Prevent cross-namespace and cluster-scoped operations.
- Block high-risk resources such as Secrets, RBAC resources, Nodes, Namespaces, PersistentVolumes, CRDs, exec, attach, and port-forward.
- Emit audit records and OpenTelemetry spans for all operations.

## Non-Goals

- Cluster administration.
- ClusterRole or ClusterRoleBinding management.
- Secret inspection or mutation.
- Pod exec, attach, or port-forward.
- Bypassing the policy engine.
- Providing raw Kubernetes credentials to Codex.

## Architecture Overview

```mermaid
flowchart LR
    Codex["Codex / MCP Client"] --> RemoteMCP["Remote MCP\nhttp://k8s-inspector.bosgenesis.local/mcp"]
    Curl["curl / BOS AI Studio / n8n"] --> REST["REST API\n/health /pods /apply /patch"]

    RemoteMCP --> App["bosgenesis-k8s-inspector-mcp Pod"]
    REST --> App

    App --> Policy["Namespace Policy Guard"]
    Policy --> Ops["Kubernetes Operation Layer"]
    Ops --> K8sClient["Kubernetes Python Client\nExplicit ServiceAccount bearer auth"]

    K8sClient --> K8sAPI["Kubernetes API Server"]
    K8sAPI --> RBAC["RoleBinding + Role\nnamespace: bosgenesis"]
    RBAC --> NS["Allowed Namespace\nbosgenesis"]

    App --> Audit["JSONL Audit Log"]
    App --> OTel["OpenTelemetry"]
    OTel --> SigNoz["SigNoz Collector"]
```

## Runtime Deployment

```mermaid
flowchart TB
    subgraph Cluster["Kubernetes Cluster"]
        subgraph NS["Namespace: bosgenesis"]
            Ingress["Ingress\nk8s-inspector.bosgenesis.local"] --> Service["Service\nbosgenesis-k8s-inspector-mcp:8080"]
            Service --> Pod["Deployment Pod\nFastAPI + MCP"]
            Pod --> SA["ServiceAccount\nbosgenesis-k8s-inspector-mcp"]
            SA --> RoleBinding["RoleBinding"]
            RoleBinding --> Role["Namespace Role"]
            Role --> Resources["Allowed namespaced resources"]
        end

        Pod --> APIServer["Kubernetes API Server"]
    end

    Codex["Codex"] --> Ingress
```

## Major Components

| Component | Responsibility |
|---|---|
| FastAPI server | Serves REST API and mounts Streamable HTTP MCP at `/mcp`. |
| FastMCP server | Exposes MCP tools for reads and governed writes. |
| Policy engine | Enforces namespace, blocked resources, supported resources, and pod safety rules. |
| Operation layer | Normalizes Kubernetes list, get, apply, create, update, patch, delete, bind, and scale operations. |
| Kubernetes client | Uses in-cluster ServiceAccount token through explicit bearer authentication. |
| Audit logger | Emits JSON audit records for allowed, denied, successful, and failed operations. |
| Telemetry | Emits OpenTelemetry spans to SigNoz when enabled. |

## Data Flow

```mermaid
sequenceDiagram
    participant C as Codex
    participant M as Remote MCP Endpoint
    participant P as Policy Guard
    participant O as Operation Layer
    participant K as Kubernetes API
    participant A as Audit Logger

    C->>M: tools/call k8s_list_pods
    M->>A: audit request started
    M->>P: validate namespace and resource
    P-->>M: allowed
    M->>O: list pods
    O->>K: list namespaced pods with ServiceAccount token
    K-->>O: pod list
    O-->>M: normalized pod summaries
    M->>A: audit success
    M-->>C: MCP tool result
```

## Security Model

Security is enforced in layers:

1. Remote clients never receive kubeconfig or cluster credentials.
2. The pod uses in-cluster ServiceAccount authentication.
3. Kubernetes RBAC is namespace-scoped to `bosgenesis`.
4. The application policy engine blocks unsafe kinds, resources, namespaces, and pod specs.
5. Mutating MCP tools require an API key tool argument.
6. REST mutating endpoints require `X-API-Key`.
7. All operations produce audit records.

## Supported Resource Scope

Allowed read resources:

- Pods
- Pod logs
- Services
- ConfigMaps
- Deployments
- ReplicaSets
- StatefulSets
- DaemonSets
- Jobs
- CronJobs
- Events
- Ingresses
- PersistentVolumeClaims

Allowed write resources when policy allows:

- Pods
- Services
- ConfigMaps
- PersistentVolumeClaims
- Deployments
- ReplicaSets
- StatefulSets
- DaemonSets
- Jobs
- CronJobs
- Ingresses

Blocked resources:

- Secrets
- ServiceAccounts
- Roles and RoleBindings
- ClusterRoles and ClusterRoleBindings
- Nodes
- Namespaces
- PersistentVolumes
- CustomResourceDefinitions
- Pods exec, attach, and port-forward

ConfigMap reads are deliberately narrower than full raw Kubernetes objects by default. List operations return metadata and key names only, and single ConfigMap reads return values only when `include_data=true` is explicitly requested. This keeps ConfigMaps useful for diagnostics while preserving the stronger Secret guardrail.

## Availability and Operations

The service is deployed as a single replica by default. It is stateless except for ephemeral audit logs mounted on an `emptyDir`. It can be horizontally scaled later if audit persistence moves to a durable backend.

## Current Deployment Endpoint

```text
http://k8s-inspector.bosgenesis.local/mcp
```

Health endpoint:

```text
http://k8s-inspector.bosgenesis.local/health
```
