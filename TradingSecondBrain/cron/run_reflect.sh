#!/usr/bin/env bash
# Weekly Sunday 23:00 reflection.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && source .env && set +a

API_URL="http://${API_HOST:-127.0.0.1}:${API_PORT:-8088}"
TOKEN="${API_TOKEN:-changeme-local-token}"

curl -fsS -X POST "$API_URL/reflect" \
  -H "X-API-Token: $TOKEN"

if [ -d "obsidian-vault/.git" ]; then
  cd obsidian-vault
  git add -A
  git commit -m "vault: auto $(date -u +%Y-%m-%dT%H:%MZ) weekly reflection" || true
fi
