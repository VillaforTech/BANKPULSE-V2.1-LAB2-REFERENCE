# Fallo de bootstrap de Grafana en CI

Run [34885025865](https://github.com/VillaforTech/bankpulse-social-split/actions/runs/34885025865), commit `8a56e4a`. Arquitectura, unitarias, despliegue, smoke, proyección y negocio pasaron. El navegador no llegó a medir eventos.

`failure.json` registra el error de página `Invalid language tag: en-US@posix`, la pantalla de archivos de Grafana sin cargar y cero conexiones WebSocket. El runner heredó una etiqueta de idioma POSIX que las APIs Intl no aceptan. La corrección declara `locale: en-US` en BrowserContext; no amplía timeouts ni cambia valores, pérdidas o el umbral p95 de 1 s. El nuevo run debe confirmar la recuperación.
