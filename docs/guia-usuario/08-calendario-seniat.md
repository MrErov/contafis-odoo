# Calendario SENIAT

## Estado de esta funcionalidad

> **Funcionalidad en roadmap.** El módulo **todavía no incluye** un modelo de calendario SENIAT con cálculo automático de vencimientos por RIF. Esta sección describe el diseño planeado y la referencia normativa. Se completará cuando la funcionalidad esté implementada.

## ¿Qué es el calendario SENIAT?

En Venezuela, el SENIAT publica cada año un calendario de vencimientos por obligación (IVA, ISLR, IGTF). Las fechas se asignan según el **último dígito del RIF** del contribuyente.

Referencia normativa vigente:

- **Providencia SNAT/2025/000091** — Gaceta Oficial N° 43.283 del 23 de diciembre de 2025.

## Cómo se usará (diseño planeado)

Cuando la funcionalidad esté lista, el flujo será:

1. El contador selecciona el cliente (con su RIF registrado)
2. El sistema toma el último dígito del RIF
3. Busca en el calendario del año la fecha del vencimiento
4. Muestra los próximos vencimientos ordenados por fecha
5. Genera alertas automáticas N días antes del vencimiento

## Tabla de vencimientos por último dígito

Las fechas publicadas por el SENIAT para 2026 siguen el patrón general:

| Último dígito RIF | Día de vencimiento (aprox.) |
|-------------------|-----------------------------|
| 0 | 15 de cada mes |
| 1 | 17 |
| 2 | 19 |
| 3 | 21 |
| 4 | 23 |
| 5 | 25 |
| 6 | 27 |
| 7 | 29 |
| 8 | 30 |
| 9 | 02 del mes siguiente |

<!-- VERIFICAR: valores exactos contra la Providencia SNAT/2025/000091 -->

## Mientras tanto

Mientras la funcionalidad no esté implementada, el contador puede:

- Consultar los vencimientos directamente en el portal del SENIAT
- Usar la sección de **Obligaciones** del módulo, que permite registrar fechas manualmente por cliente
- Recibir recordatorios por email si configura la sección de [Alertas](./10-alertas.md)

## Siguiente paso

> Continúa con [Cartelera fiscal](./09-cartelera-fiscal.md).
