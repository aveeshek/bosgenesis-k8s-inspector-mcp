#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://k8s-inspector.bosgenesis.local}"
API_KEY="${API_KEY:-replace-me-before-deploy}"
cat <<'JSON' | curl -sS -X POST "${API}/apply" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d @- | python -m json.tool
{
  "dry_run": true,
  "actor": "codex",
  "manifest": {
    "apiVersion": "v1",
    "kind": "ConfigMap",
    "metadata": {
      "name": "codex-demo-config",
      "namespace": "bosgenesis"
    },
    "data": {
      "message": "hello from namespace-scoped mcp"
    }
  }
}
JSON
