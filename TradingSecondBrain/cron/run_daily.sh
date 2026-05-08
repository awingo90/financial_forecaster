#!/usr/bin/env bash
# Trigger the daily 06:00 brief.
# Works whether the agent API is running natively or via docker-compose.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && source .env && set +a

API_URL="http://${API_HOST:-127.0.0.1}:${API_PORT:-8088}"
TOKEN="${API_TOKEN:-changeme-local-token}"

# 1. Re-embed any new vault notes (idempotent).
curl -fsS -X POST "$API_URL/ingest" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" || echo "ingest failed (continuing)"

# 2. Generate the brief.
curl -fsS -X POST "$API_URL/brief" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"horizon":"swing","force_refresh":false}'

# 3. Auto-commit the vault if it's a git repo.
if [ -d "obsidian-vault/.git" ]; then
  cd obsidian-vault
  git add -A
  git commit -m "vault: auto $(date -u +%Y-%m-%dT%H:%MZ) daily brief" || true
fi
