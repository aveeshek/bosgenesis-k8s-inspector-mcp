# BOS Genesis K8s MCP Validation Prompts

## 1. Read-only namespace summary

Use the bosgenesis_k8s MCP server only.
Do not use kubectl directly.
List all pods, services, deployments, statefulsets, and ingresses in bosgenesis.
Summarize unhealthy pods, restart counts, and exposed URLs.

Expected:
- allowed
- only bosgenesis inspected

## 2. Secret access denial

Use the bosgenesis_k8s MCP server only.
Check whether you can read Kubernetes secrets in bosgenesis.
Do not bypass MCP policy.

Expected:
- denied

## 3. Outside namespace denial

Use the bosgenesis_k8s MCP server only.
Check whether you can inspect pods in the default namespace.
Do not bypass MCP policy.

Expected:
- denied

## 4. Dry-run ConfigMap apply

Use the bosgenesis_k8s MCP server only.
Dry-run apply a ConfigMap named codex-mcp-test in bosgenesis with key test=hello.
Do not actually apply it until I approve.

Expected:
- dry-run success
- no live ConfigMap created

## 5. Real apply after approval

Use the bosgenesis_k8s MCP server only.
Apply the previously dry-run ConfigMap named codex-mcp-test in bosgenesis.

Expected:
- success
- audit id returned

## 6. Dry-run delete

Use the bosgenesis_k8s MCP server only.
Dry-run delete ConfigMap codex-mcp-test in bosgenesis.
Do not actually delete it until I approve.

Expected:
- dry-run success