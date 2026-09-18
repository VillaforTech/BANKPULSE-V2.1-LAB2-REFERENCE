# Versión sana: CI completo verde

[PR #1](https://github.com/VillaforTech/bankpulse-social-split/pull/1), [run 34886628779](https://github.com/VillaforTech/bankpulse-social-split/actions/runs/34886628779), SHA `3fcfa686dcedf5b41ec6f0cf152ddcb7f21fccb0`. Todos los jobs y el Release gate terminaron success.

- Negocio: 29/29; resiliencia: 8/8. `current-state.json` conserva seis servicios HTTP 200 / UP después de las pruebas y el SHA observado.
- Navegador Ubuntu: Playwright 1.55.1 / Chromium 140.0.7339.186. 100/100 muestras correlacionadas, sin pérdida ni error de muestra/página. p50 832.1 ms, p95 945.4 ms, máximo 1931.9 ms; cuatro muestras alcanzan o superan 1 s. El criterio es p95 ≤1 s, no máximo ≤1 s.
- El contador cambia; B-K1 se mantiene en 100 y ambos renderizan el mismo evento/revisión con calidad VIGENTE. Este benchmark mide entrega y render bajo esa carga secuencial, no toda combinación de cambios numéricos ni carga productiva.
- Desconexión: revisión 746 vigente → 746 desactualizada → 757 vigente, misma pestaña sin reload. El log conserva una advertencia de performance de Grafana y dos errores de red provocados por el modo offline; no se presentan como cero mensajes de consola.
- Resiliencia: corte inicial 108 agregados / 132 eventos, outbox 3→0; tras la interrupción, 109 / 133 y outbox 0. Reinicio y replay no duplican eventos. El vencimiento se persistió 260.533 ms después del límite de 120 s y se observó 508.035 ms después, sin nueva operación de negocio.

Las capturas/JSON conservan fixtures demo. No acreditan pagos reales, un merge ni una ejecución en GitHub Codespaces. Esta selección permanece disponible aunque expire el artifact temporal de GitHub Actions.
