# BankPulse: referencia completa de El Falso Verde

Este **gemelo académico independiente** parte de [BANKPULSE-V2.1-LAB2](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2), conserva sus seis servicios y el historial ADR, y desarrolla la solución de referencia de Roberto Villafuerte para CMP4008. No sustituye los aportes ni los PR del equipo. Revisar y adaptar sus cambios antes de integrarlos en el repositorio original.

**Laboratorio:** cuentas, importes, referencias y autorizaciones son demo. Payments registra `ACCEPTED`; no demuestra un cobro o liquidación financiera real. Los KPIs expresan integridad y exposición del laboratorio.

## Arrancar y parar el gemelo

Requisitos: Docker Compose v2; objetivo local 8 GB RAM para Docker. Construcciones simultáneas limitadas a dos. Los servicios Java tienen límite de memoria y heap explícitos.

```bash
COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT=2 docker compose build
docker compose up -d --wait --wait-timeout 300
docker compose -f observability/compose.yaml up -d prometheus grafana
bash scripts/readiness.sh
```

| Acceso local | URL |
|---|---|
| Consola y APIs | http://localhost:18080 |
| Grafana, panel de negocio Live | http://localhost:13000/d/bankpulse-business |
| Prometheus | http://localhost:19090 |
| cAdvisor opcional | http://localhost:18088 |
| Snapshot completo | http://localhost:18080/api/business/snapshot |

Grafana ofrece Viewer anónimo exclusivamente en el laboratorio ligado a loopback. El publicador usa las credenciales demo de Compose, nunca una credencial real. No exponer estos servicios a Internet. Los proyectos, red y volúmenes contienen `bankpulse-reference`; no comparten los recursos del original. Las bases no publican puertos al host.

```bash
docker compose -f observability/compose.yaml down
docker compose down
```

La parada conserva volúmenes e historia. No usar `down -v` para aparentar recuperación. Para un laboratorio nuevo, usar otro entorno aislado; los scripts de prueba identifican sus propias fixtures.

## Probar un cierre

La consola permite total USD 100 y tres participantes: reparte 33,34 + 33,33 + 33,33. Autorizar cada cuota genera una referencia demo y permite cerrar cuando la suma coincide. También puede reproducirse todo por API:

```bash
bash scripts/smoke-v2.sh
bash scripts/business-test.sh
```

El segundo comando crea fixtures independientes: 60+40 cierra; 60+30, 60+50, falta de consentimiento y sesión vacía se rechazan. Conserva JSON de observación en `artifacts/business/result.json` y retorna un código de fallo si el negocio incumple, aunque health esté UP.

## Arquitectura y aceptación

Social Split confirma su estado y outbox en PostgreSQL. Un relay publica hechos en Redpanda; `business-analytics` mantiene una proyección y checkpoints en su propio esquema. Calcula tres KPIs con temporizadores de 250 ms, guarda snapshots y publica a Grafana Live. Prometheus conserva series históricas y salud. El panel local incluye revisión, evento, cobertura y un watchdog de heartbeat; un dato congelado pasa a DESACTUALIZADO.

- [Contrato de eventos](docs/events-deber-01.md)
- [Definiciones de KPIs](docs/kpis-deber-01.md)
- [Deber, diagnóstico y evidencia](docs/deber-01.md)
- [Operación de Grafana Live](observability/README.md)
- [ADR y ownership](docs/adr/README.md)

## Validación reproducible

```bash
bash scripts/unit-test.sh
bash scripts/projection-test.sh
python3 scripts/resilience_test.py
npm ci
npx playwright install --with-deps chromium
npm run browser-test
```

Resiliencia tarda aproximadamente dos minutos: corta el broker, conserva un commit en el outbox, recupera, reinicia analítica, repite un evento real y observa un vencimiento de 120 s sin nuevas acciones. Las pruebas de proyección usan exclusivamente el esquema `analytics_contract_test`.

El navegador ejecuta **al menos 100 operaciones secuenciales**, comprueba ID y número visible, calidad VIGENTE, y mide con `performance.now()` de la misma página hasta dos frames posteriores al render. Registra todas las pérdidas y errores; p95 >1 s bloquea. También desconecta y reconecta la misma pestaña. `artifacts/browser/` contiene muestras y capturas. No ejecutar otra carga de negocio mientras corre esa medición.

## Correspondencia con issues del equipo

| Issue original | Referencia ejecutable |
|---|---|
| [#1 Dominio/eventos](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2/issues/1) | `services/social-split-api`, contratos en `docs/`, tests JUnit y business test |
| [#2 Analítica](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2/issues/2) | `services/business-analytics`, tests de reloj, proyección y replay |
| [#3 Panel Live](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2/issues/3) | dashboard, plugin local y `scripts/browser-test.mjs` |
| [#4 Integración/gate](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2/issues/4) | Compose aislado, readiness y `.github/workflows/ci.yml` |
| [#5 Evidencia](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2/issues/5) | business, resiliencia, navegador y `docs/deber-01.md` |

Estas rutas muestran la implementación de referencia, no el aporte ni el cierre del issue de otro integrante. Los checks CI y sus artifacts constituyen evidencia de cada revisión concreta.

## Git y Codespaces

`origin` pertenece a **BANKPULSE-V2.1-LAB2-REFERENCE**; `upstream` es el original y su push está deshabilitado en el checkout preparado. Todo trabajo del gemelo se propone a su propio `main`; no copiar instrucciones antiguas para pushear al repositorio compartido. El check requerido se llama **Release gate**.

Un Codespace limpio usa los mismos comandos y puertos reenviados 18080/13000/19090/18088. [Guía de Codespaces](docs/CODESPACES_REFERENCE.md). Una ejecución local no acredita que otro integrante haya reproducido un Codespace: esa verificación se registra aparte en la evidencia.
