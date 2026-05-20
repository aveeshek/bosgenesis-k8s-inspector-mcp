#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://k8s-inspector.bosgenesis.local}"
API_KEY="${API_KEY:-replace-me-before-deploy}"
curl -sS -H "X-API-Key: ${API_KEY}" "${API}/namespace/summary" | python -m json.tool
