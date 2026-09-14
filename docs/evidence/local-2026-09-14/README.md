# Evidencia local de desarrollo · 14 de septiembre de 2026

Referencia candidata `5a40e4b`; entorno macOS, Docker Desktop (VM 8 GB / 12 CPU), Chrome 152.0.7977.84. La corrida de Ubuntu queda registrada por GitHub Actions en su propio SHA y artifacts. Los JSON son fixtures demo; no prueban pagos reales.

- API/business: 29 comprobaciones correctas, con persistencia y Audit correlacionados.
- Java: 10 tests, incluidos dos fallos de escritura del outbox que revierten estado y versión.
- ADR: 7 tests; panel: 7; KPIs: 4. Proyección SQL: 5 pruebas adicionales en esquema aislado (el comando muestra 9 porque repite los cuatro tests puros).
- Resiliencia: 8 comprobaciones. El vencimiento de 120 s apareció en historial persistido a los 0.085 s del límite, sin nuevos eventos de negocio.
- Navegador: 100/100 eventos observados, cero pérdidas y errores; p50 848.2 ms, p95 915.5 ms, máximo 1116.3 ms. El requisito es p95 ≤ 1 s; se conserva el máximo superior a un segundo.
- Cada muestra incluye contador y B-K1 visibles, mismos evento y revisión, calidad VIGENTE y dos frames hasta t1. La desconexión invalida los números; la misma pestaña recupera sin reload.
- La captura de consola se repitió después de esperar que su animación terminara; conserva su JSON de cierre propio y no modifica el conjunto de 100 muestras.

En el panel, el backlog de 720 USD demo corresponde a fixtures negativos y de resiliencia que siguen abiertos. La alerta roja se conserva aunque los cierres válidos tengan integridad 100%.

Los primeros artifacts exploratorios permanecen fuera de esta selección bajo `artifacts/browser` y `artifacts/browser-100`; no se presentan como la medición estricta. CI y reproducción humana en Codespaces deben observarse por separado.
