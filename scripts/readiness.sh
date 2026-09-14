#!/usr/bin/env bash
set -euo pipefail
base="${BANKPULSE_URL:-http://localhost:18080}"
for route in health/payments health/audit health/experiences health/travel health/events health/social-split health/business; do
  curl --retry 30 --retry-delay 1 --retry-all-errors --fail --silent --show-error "$base/$route" >/dev/null
done
curl --retry 30 --retry-delay 1 --retry-all-errors --fail --silent --show-error "${GRAFANA_URL:-http://localhost:13000}/api/health" >/dev/null
curl --retry 30 --retry-delay 1 --retry-all-errors --fail --silent --show-error "${PROMETHEUS_URL:-http://localhost:19090}/-/healthy" >/dev/null
