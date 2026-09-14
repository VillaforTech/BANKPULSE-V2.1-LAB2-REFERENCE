#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests/adr -v
node scripts/panel-test.mjs
for service in payments-api social-split-api; do
  docker run --rm --memory=768m -v "$PWD/services/$service:/workspace" -v bankpulse-reference-maven:/root/.m2 -w /workspace maven:3.9.9-eclipse-temurin-21 mvn -B test
 done
docker compose run --rm --no-deps business-analytics pytest -q
