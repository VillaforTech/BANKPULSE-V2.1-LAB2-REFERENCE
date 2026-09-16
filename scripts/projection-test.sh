#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T postgres psql -U bankpulse_admin -d bankpulse_domains -c 'CREATE SCHEMA IF NOT EXISTS analytics_contract_test AUTHORIZATION analytics_owner;'
docker compose run --rm --no-deps -e 'ANALYTICS_DSN=postgresql://analytics_owner:analytics_reference_local@postgres:5432/bankpulse_domains?options=-csearch_path%3Danalytics_contract_test' business-analytics pytest -q -p no:cacheprovider
