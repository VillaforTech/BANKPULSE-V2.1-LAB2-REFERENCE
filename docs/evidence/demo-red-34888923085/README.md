# Demostración roja: infraestructura UP, negocio incorrecto y PR bloqueado

[PR #2](https://github.com/VillaforTech/bankpulse-social-split/pull/2), [run 34888923085](https://github.com/VillaforTech/bankpulse-social-split/actions/runs/34888923085), SHA congelado `90745a4a58a84078b8557c0616dd8df5764ba2a6`. Su base sana exacta es `3fcfa68`; PR #1 aún no estaba integrado al crear esta rama. El delta contra esa base es una sola línea que desactiva la comparación de suma; no cambia tests ni el consumidor.

`business.json` contiene cuatro comprobaciones rojas: no se rechazan under/over y ambos presentan cierres indebidos. Under `3aecd371-d131-4853-9570-e37bc11c9781` responde HTTP 200, persiste COMPLETED con total 100 y cuotas 60 + 30. Over `7caf8ae1-9532-4950-b76b-bbeff445b540` hace lo mismo con 60 + 50. Cada cohorte individual muestra B-K1 = 0% y B-K2 = 10.00 USD demo. Las dos pruebas de dominio de suma fallan con la misma causa.

`current-state.json` vuelve a consultar los agregados y KPIs y registra seis servicios HTTP 200 / UP a las 19:52:31–32 UTC en ese mismo SHA. La captura real de Grafana muestra datos vigentes y cobertura completa, con alerta: integridad global 50% y descuadre global 20. El global combina los dos cierres inválidos con dos válidos; no se confunde con cada cohorte individual.

El navegador todavía pasa sus 100 renders (p95 878.4 ms; máximo 1338.8 ms). Eso demuestra entrega del valor incorrecto y no vuelve sano al negocio. Resiliencia se omite porque negocio falló; la omisión también impide aceptar el run completo. `Release gate` falla.

`github-summary.json` conserva la observación independiente de GitHub a las 20:10:30 UTC: PR ready, OPEN, mismo SHA que el run, mergeStateStatus BLOCKED y check requerido Release gate fallido. `github-pr.json`, `github-run.json` y `github-protection.json` permiten verificar la conclusión; las reglas del original no se modificaron.

La corrección restaura la condición en este mismo PR. Su ejecución posterior se enlaza en el cuerpo del PR y debe pasar antes de cualquier integración. Los artifacts rojos se conservan tal como fueron observados; no se borran fixtures para ocultar el defecto.

`red-business-review.json` conserva la revisión independiente y los hashes de los artifacts originales. Sus rutas se refieren a la descarga original; los nombres seleccionados aquí se relacionan por contenido/hash y tienen su propio manifiesto.
