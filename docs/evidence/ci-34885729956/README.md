# CI de diagnóstico: navegador verificado y baseline de resiliencia prematuro

[Run 34885729956](https://github.com/VillaforTech/BANKPULSE-V2.1-LAB2-REFERENCE/actions/runs/34885729956), SHA `bf01463899fae24eb118cad76972d9c07300a8ae`, 14 de septiembre de 2026. **El run completo falló**; esta selección no representa aceptación final.

El locale explícito `en-US` permitió arrancar Grafana en Ubuntu. Playwright 1.55.1 / Chromium 140.0.7339.186 observó 100 de 100 eventos, sin pérdidas, errores ni errores de página: p50 848.6 ms, p95 882.2 ms, máximo 915.2 ms. `latency.json` conserva las muestras, sus valores visibles, UTC, computedAt y revisiones antes/después de desconexión. Las tres capturas corresponden a la misma pestaña, sin reload.

Arquitectura, unit, smoke, SQL y negocio también pasaron. Resiliencia falló porque su precondición aceptaba cualquier snapshot FRESH: guardó 107 agregados / 129 eventos justo después de crear una fixture cuyos tres eventos todavía no estaban en ese corte. El outbox posterior registra 109 / 133; `current-state.json` confirma 109 / 133 tras recuperar el broker, con cobertura completa. Se conserva el resultado rojo original en `resilience-result.json`; no se reemplaza por un PASS inferido.

La corrección posterior exige que propietario y proyección coincidan con el corte comprometido después de crear la fixture, incluyendo outbox drenado, antes de comparar la recuperación. Conserva esperas acotadas y la igualdad de no pérdida. Su ejecución completa debe verificarse en un run posterior.
