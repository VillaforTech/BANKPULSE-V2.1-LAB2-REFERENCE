#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[BankPulse] Created a private .env from the laboratory template."
fi

# The two Compose entrypoints read their own .env. Keep exact forwarded origins,
# never a wildcard, so the browser's WebSocket Origin matches Grafana Live.
if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  grafana_origin="https://${CODESPACE_NAME}-13000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  console_origin="https://${CODESPACE_NAME}-18080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  local_origins="http://localhost:13000,http://127.0.0.1:13000"
  local_origins+=",http://localhost:18080,http://127.0.0.1:18080"
  {
    printf 'GRAFANA_ROOT_URL=%s/\n' "$grafana_origin"
    printf 'GRAFANA_LIVE_ORIGINS=%s,%s,%s\n' "$local_origins" "$grafana_origin" "$console_origin"
  } > observability/.env
fi

echo "[BankPulse] Building Java services and the operations console..."
COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT=2 docker compose build
echo "[BankPulse] Build complete. The stack will start automatically."
