#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://k8s-inspector.bosgenesis.local}"
API_KEY="${API_KEY:-replace-me-before-deploy}"
cat <<'JSON' | curl -sS -X POST "${API}/delete" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d @- | python -m json.tool
{
  "resource": "configmaps",
  "name": "codex-demo-config",
  "namespace": "bosgenesis",
  "dry_run": true,
  "actor": "codex"
}
JSON
