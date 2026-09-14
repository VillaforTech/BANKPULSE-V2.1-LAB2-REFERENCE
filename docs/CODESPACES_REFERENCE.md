# Reproducir la referencia en Codespaces

Crear un Codespace desde **BANKPULSE-V2.1-LAB2-REFERENCE**, seleccionando la rama o el commit que se evalúa. El devcontainer declara Java 21, Node 22, Python 3.12, Docker-in-Docker y GitHub CLI. Recursos objetivo: 4 CPU y 8 GB. No usar el repositorio compartido ni sus puertos. `postCreateCommand` construye; `postStartCommand` arranca. Puertos reenviados: 18080, 13000, 19090 y 18088; conservar visibilidad privada.

```bash
docker compose config --quiet
COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT=2 docker compose build
docker compose up -d --wait --wait-timeout 300
docker compose -f observability/compose.yaml up -d prometheus grafana
bash scripts/readiness.sh
bash scripts/unit-test.sh
bash scripts/projection-test.sh
bash scripts/smoke-v2.sh
bash scripts/business-test.sh
python3 scripts/resilience_test.py
npm ci
npx playwright install --with-deps chromium
npm run browser-test
```

La consola ajusta enlaces de puertos al hostname de Codespaces. El script de preparación genera `observability/.env` con `GRAFANA_ROOT_URL` y los dos orígenes HTTPS exactos de los puertos 13000 y 18080. Si cambian las URLs, volver a ejecutar el setup y recrear Grafana; no usar un wildcard. La prueba de navegador se ejecuta dentro del Codespace contra localhost; sus conexiones no dependen del proxy de puertos externo. Las URLs de API/snapshot pueden sustituirse mediante variables de entorno.

Conservar artifacts y registrar SHA, comandos, recursos, resultado y autor de la reproducción. Un run local o CI no se rotula como reproducción humana de Codespace si nadie la realizó.

## Alcance de la verificación

Estos comandos definen la reproducción solicitada. Las pruebas locales y de GitHub Actions se registran por separado en [la evidencia del deber](deber-01.md). La ejecución en un Codespace limpio todavía no está confirmada; no se atribuye una reproducción a otro integrante sin observarla.
