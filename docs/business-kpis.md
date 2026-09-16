# KPIs propios de Social Split

Son parámetros de demostración, no compromisos de servicio ni garantías financieras. Fuente: hechos confirmados por Social Split y una proyección propia de analítica. Reloj: UTC; cálculo con Decimal. La ventana es `(ahora - 15 minutos, ahora]`, usando `closedAt`, nunca el instante de recepción. Monedas separadas. El dashboard predeterminado selecciona USD; la opción Moneda del panel permite otra moneda sin cambiar su fórmula.

| KPI | Población y fórmula | Unidad / estado sano |
|---|---|---|
| B-K1 Cierres íntegros | 100 × cierres válidos / cierres de la ventana. Válido: participantes, cuotas positivas, suma exacta, autorizaciones y referencias no vacías. | Porcentaje; 100 %. Denominador cero: valor null, NO_SAMPLE / SIN MUESTRA. |
| B-K2 Descuadre | Suma de abs(total - suma de cuotas autorizadas) de los cierres de la misma ventana. | Moneda de cada sesión; 0. Sin cierres: NO_SAMPLE, suma vacía 0 explícita. |
| B-K3 Autorizado sin resolución | Suma de cuotas autorizadas de TODO el backlog OPEN con `createdAt < ahora - 120 s`. No se limita a la ventana. | Moneda; 0. Importe demo comprometido, no pérdida real. |

La edad exactamente 120 s todavía no está vencida. Los timers recalculan desde estado y reloj; no agregan repetidamente el mismo importe. Una sesión cerrada deja de aportar backlog. Un cierre incorrecto histórico permanece en B-K1/B-K2 hasta salir de la ventana; no se elimina para aparentar recuperación.

Calidad FRESH exige consumidor conectado, polling reciente, lag cero, outbox drenado, sin huecos/rechazos y cobertura contrastada con Social Split. INCOMPLETE impide presentar una cifra como global válida. El panel añade un watchdog de 2,5 s sin avance local del heartbeat y muestra DESACTUALIZADO aunque Grafana siga abierto. SIN MUESTRA es neutro y no equivale a cumplimiento.

Alertas visibles: B-K1 < 100 (con muestra), B-K2 > 0, B-K3 > 0. Resolución se calcula desde el estado actual; los negativos del business test permanecen OPEN y pueden generar backlog después de 120 s. Eso es una alerta esperada, no un error que deba ocultarse.

Fixtures: sano 100 = 60 + 40; rechazados 60 + 30 y 60 + 50; mutación 100 = 60 + 30 cerrada produce B-K1 = 0 y B-K2 = 10 en su cohorte individual; OPEN con 60 autorizados produce B-K3 = 60 después de 120 s. Tests de reloj prueban expiración sin eventos y separación EUR/USD. Resiliencia observa además un vencimiento real de 120 s.
