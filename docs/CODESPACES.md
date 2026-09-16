# Ejecutar el gemelo BankPulse en Codespaces

Esta guía corresponde a [BANKPULSE-V2.1-LAB2-REFERENCE](https://github.com/VillaforTech/bankpulse-reference). No hay que subir otra copia ni trabajar sobre el repositorio compartido. Los datos, cuentas y autorizaciones son demo; cada Codespace conserva sus propias bases y red.

La reproducción completa en un Codespace limpio pasó el 15 de septiembre de 2026: [evidencia cloud](evidence/codespaces-20260915/README.md). Se verificaron 100/100 renders, p95 358 ms, negocio y recuperación. Esto acredita la ejecución asistida de Roberto; no la reproducción de otro integrante.

## Crear y arrancar

1. Iniciar sesión en GitHub, abrir el gemelo y seleccionar **Code → Codespaces → Create codespace**. Elegir la rama o revisión que se va a evaluar; registrar el SHA con `git rev-parse HEAD`.
2. Usar como objetivo 4 CPU, 8 GB de RAM y 32 GB de disco, tal como declara `.devcontainer/devcontainer.json`.
3. Esperar a que termine `postCreateCommand` (`.devcontainer/setup.sh`): prepara los archivos locales de entorno y construye los servicios con un máximo de dos builds simultáneos.
4. Esperar `postStartCommand` (`.devcontainer/start-lab.sh`): arranca la plataforma y exige sus health checks. Después iniciar observabilidad, que usa otro archivo Compose:

```bash
docker compose -f observability/compose.yaml up -d prometheus grafana
bash scripts/readiness.sh
```

Si se necesita ejecutar manualmente los pasos del devcontainer, desde la raíz del gemelo:

```bash
bash .devcontainer/setup.sh
bash .devcontainer/start-lab.sh
docker compose -f observability/compose.yaml up -d prometheus grafana
bash scripts/readiness.sh
```

El devcontainer incluye Java 21, Node 22, Python 3.12, Docker-in-Docker y GitHub CLI. La primera construcción descarga imágenes y dependencias; revisar el error real si un paso falla antes de repetirlo.

## Abrir la consola y el panel

En la pestaña **Ports**, mantener visibilidad **Private** y usar el enlace reenviado de cada puerto:

| Puerto | Contenido | Ruta |
|---|---|---|
| 18080 | Consola demo y APIs | `/` |
| 13000 | Grafana Live | `/d/bankpulse-business` |
| 19090 | Prometheus | `/` |
| 18088 | cAdvisor opcional; no se inicia en los comandos anteriores | `/` |

Las bases no publican puertos al host. La consola adapta sus enlaces al hostname de Codespaces. El setup escribe `observability/.env` con el root URL de Grafana, los dos orígenes HTTPS exactos para 13000 y 18080, y los orígenes loopback del harness interno; no usa wildcard. Si cambian las URLs, repetir el setup y recrear Grafana:

```bash
docker compose -f observability/compose.yaml up -d --force-recreate grafana
```

Desde el terminal del Codespace las pruebas usan `http://localhost:18080` y `http://localhost:13000`. El navegador humano entra por los enlaces privados de GitHub. Esos recorridos se verifican por separado: el benchmark interno no prueba por sí solo el proxy, el login ni el WebSocket externo de Codespaces.

## Verificar el laboratorio

```bash
bash scripts/unit-test.sh
bash scripts/projection-test.sh
bash scripts/smoke-v2.sh
bash scripts/business-test.sh
npm ci
npx playwright install --with-deps chromium
npm run browser-test
python3 scripts/resilience_test.py
```

El smoke mantiene la comparación del pago idempotente. Negocio comprueba cierre válido e inválidos por API y persistencia. Proyección usa un esquema SQL aislado. El navegador crea al menos 100 operaciones y mide hasta el render correlacionado de las tarjetas, con p95 ≤1 s, cero pérdidas y recuperación de la misma pestaña; no generar otras fixtures durante esa medición. Resiliencia interrumpe el broker, reinicia analítica y observa el vencimiento real de 120 s sin tráfico nuevo, conservando volúmenes e historia.

Revisión manual: abrir la consola, elegir total USD 100 y tres participantes, autorizar las tres cuotas y cerrar. Deben mostrarse 33,34 + 33,33 + 33,33 y estado COMPLETED. En Grafana deben avanzar revisión y timestamp aunque el auto-refresh esté apagado; si faltan cobertura o heartbeats, los valores dejan de presentarse como vigentes.

Guardar `artifacts/`, SHA, comandos, recursos, identidad de quien reprodujo y resultado. La reproducción del navegador humano debe incluir los enlaces privados, el panel realmente abierto y su conexión Live; no guardar credenciales ni tokens. [Evidencia y alcance de la validación](business-verification.md).

## Parar y reanudar

```bash
docker compose -f observability/compose.yaml down
docker compose down
```

Estos comandos conservan los volúmenes. Para reanudar, ejecutar el script de inicio y levantar observabilidad como arriba. No usar `down -v` para aparentar recuperación. Al terminar, detener también el Codespace desde GitHub; parar los contenedores no detiene el entorno cloud.
