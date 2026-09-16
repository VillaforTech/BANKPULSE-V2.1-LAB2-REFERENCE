# Contrato de hechos Social Split v1

Fuente: `social-split-api`. Topic final `bankpulse.social-split.events.v1`, clave Kafka `aggregateId`. Social Split es el único dueño del agregado; cada cambio bloquea su fila durante la transacción. `aggregateVersion` aumenta solo al modificar el negocio. Cierre repetido y autorización idéntica no producen otra versión. `lastEventId` persistido en la respuesta enlaza API y panel.

Estructura de evento compartida con LogistPulse, con datos propios de cada dominio:

```json
{
  "schemaVersion": 1,
  "eventId": "UUID",
  "eventType": "SPLIT_COMPLETED",
  "aggregateType": "SplitSession",
  "aggregateId": "UUID",
  "aggregateVersion": 6,
  "occurredAt": "2026-09-14T18:00:00.123Z",
  "correlationId": "request-or-event-id",
  "fixtureRunId": "business-run-healthy",
  "data": {
    "id": "UUID",
    "aggregateVersion": 6,
    "hostMemberId": "HOST-DEMO",
    "totalAmount": "100.00",
    "currency": "USD",
    "status": "COMPLETED",
    "createdAt": "2026-09-14T17:59:50.123Z",
    "updatedAt": "2026-09-14T18:00:00.123Z",
    "closedAt": "2026-09-14T18:00:00.123Z",
    "fixtureRunId": "business-run-healthy",
    "participants": [
      {
        "id": "P1",
        "memberId": "DEMO1",
        "shareAmount": "60.00",
        "authorized": true,
        "paymentReference": "DEMO1"
      },
      {
        "id": "P2",
        "memberId": "DEMO2",
        "shareAmount": "40.00",
        "authorized": true,
        "paymentReference": "DEMO2"
      }
    ]
  }
}
```

Tipos finales: `SPLIT_CREATED`, `PARTICIPANT_ADDED`, `PARTICIPANT_AUTHORIZED`, `SPLIT_COMPLETED`. Son nombres definitivos de la referencia para los conceptos inicialmente propuestos en CamelCase. `data` contiene el estado posterior completo; no se confía en una bandera `valid=true`. Importes: cadenas decimales finitas con dos posiciones. Timestamps con zona UTC; dominio persiste precisión de milisegundos. Los identificadores de miembro/referencia son exclusivamente fixtures demo; no usar datos personales o financieros reales.

## Commit, entrega y replay

El estado y su registro en el outbox se confirman en la misma transacción. El relay ordena por secuencia del outbox, espera confirmación de Kafka y marca publicado después; puede repetir un `eventId` tras una interrupción. La entrega admite duplicados; la proyección evita contarlos dos veces. El outbox financiero Payments→Audit sigue separado.

Analítica registra evento, versión de proyección y checkpoint en una transacción propia antes de confirmar el offset de Kafka. Duplicado idéntico no suma otro evento; versión antigua no reemplaza una nueva. Un ID o versión reutilizados con contenido distinto se rechazan. Un hueco de versiones mantiene cobertura INCOMPLETA hasta recibir las versiones faltantes. Los rechazos conservan causa y offset de forma durable; el cursor puede avanzar sin fingir cobertura correcta.

En este laboratorio nuevo, cobertura empieza con el primer evento. Se compara cantidad de agregados y suma de versiones con el endpoint del servicio dueño, además de lag, outbox y huecos. Datos previos sin eventos o fechas de cierre producen INCOMPLETO. No se reconstruyen fechas inventadas ni se leen tablas ajenas desde un servicio. El endpoint `/api/splits/snapshot` facilita inspección, pero **no se presenta como exportación atómica de una población concurrente ni se usa para bootstrap automático**. Recuperación ordinaria: mismo volumen/checkpoint o replay del topic conservado desde el inicio; una retención insuficiente requiere reconciliación explícita, no reset silencioso.

## Snapshot confirmado y streaming

`GET /api/business/snapshot[?fixtureRunId=...]` devuelve `schemaVersion`, `snapshotId`, `revision` monotónica persistida, `computedAt`, `sourceEventId`, `watermark`, `quality`, `coverage`, `kpis` y estado de stream. La revisión identifica el cálculo, no un evento nuevo. El filtro de fixture no recorta la comprobación global de cobertura.

Los snapshots completos y el heartbeat se publican cada 250 ms y después de un evento. Un bloqueo local ordena publicación; el panel descarta revisiones no crecientes y filtra moneda. `sourceEventId` y watermark se derivan del registro durable, no del último duplicado recibido. Grafana Live no es almacenamiento: un cliente nuevo o reconectado recibe el próximo snapshot completo. El historial reciente persiste en la base propia; se conservan 10.000 snapshots y Prometheus provee series temporales adicionales.
