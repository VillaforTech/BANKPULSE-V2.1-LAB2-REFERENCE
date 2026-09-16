# Observabilidad del gemelo

Arrancar primero la aplicación y luego `docker compose -f observability/compose.yaml up -d prometheus grafana`. Panel: http://localhost:13000/d/bankpulse-business. Auto-refresh queda apagado. Prometheus 19090 conserva salud/historial; sus scrapes no actualizan el panel Live.

## Recorrido real

API → outbox PostgreSQL → Redpanda → consumidor/estado PostgreSQL → snapshot → HTTP `POST /api/live/push/bankpulse` → canal `stream/bankpulse/business` → panel.

El push usa **Influx line protocol**, timestamp Unix nanosegundos y credenciales demo internas; no JSON. La consulta del datasource Grafana usa `queryType: measurements`. Versión de Grafana fijada en 11.6.0. [Protocolo oficial](https://grafana.com/docs/grafana/latest/setup-grafana/set-up-grafana-live/).

El plugin local `bankpulse-business-panel` tiene su fuente legible versionada. Se permite únicamente este plugin sin firma en el laboratorio. No instala código externo en tiempo de ejecución. Lee campos del frame, moneda y revisión; rechaza revisiones antiguas, comprueba muestra/calidad y vence con un reloj local si no llegan revisiones durante 2,5 s. Viewer anónimo está limitado por el bind 127.0.0.1; no usar esta configuración como servicio público.

El heartbeat entrega un snapshot completo vigente a clientes nuevos/reconectados; Live no promete replay durable. El historial REST y Prometheus tienen funciones distintas. Un panel sin muestra no conserva el 100% anterior. No se presenta una actualización recibida en el backend como medición visual.

## Evidencia

`npm run browser-test` verifica al menos 100 operaciones, valor visible, revisión, evento y calidad. Guarda muestras con reloj de la misma página, p50/p95/máximo, pérdidas y errores. La prueba falla con cualquier actualización perdida, error de página o p95 > 1 s. Desconecta y reconecta la misma pestaña, sin usar reload como recuperación. Capturas: vivo, desconectado y recuperado.

Para una comparación válida, ejecutar sin otra carga de negocio concurrente. Recursos y resultados concretos están en `docs/business-verification.md`. La primera prueba exploratoria puede distinguirse del benchmark de aceptación; no reemplazar artifacts que exhiben limitaciones.
