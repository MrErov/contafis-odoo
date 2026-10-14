# Exportar y respaldar datos

## ¿Qué se puede exportar?

- Libro de Compras/Ventas a Excel
- Planilla IVA 99030 a Excel (Forma 99030)
- Reporte de cumplimiento por cliente (PDF)
- Reporte de cartelera por cliente (PDF)

## Exportar el libro de compras/ventas

Ver [Libro de Compras y Ventas](./05-libro-compras-ventas.md), sección "Exportar el libro".

## Exportar la planilla IVA 99030

Ver [Planilla IVA 99030](./06-planilla-iva-99030.md), sección "Exportar la planilla".

## Exportar un reporte de cumplimiento

Ruta: *Cliente → botón [Imprimir Reporte]*

Incluye: datos del cliente, obligaciones, estado de cumplimiento, puntuación y alertas pendientes.

## Exportar el reporte de cartelera

Ruta: *Cumplimiento VE → Snapshots Cartelera*

Muestra el estado de los 36 documentos legales del cliente en el mes seleccionado.

## Respaldos de la base de datos

> **Importante:** el módulo NO hace respaldos automáticos de la base de datos. El respaldo debe hacerse a nivel de PostgreSQL (por ejemplo `pg_dump`) o mediante el módulo de respaldos de Odoo. Ver [Limitaciones conocidas](./anexo-limitaciones.md).

## Respaldos de documentos adjuntos

Los archivos adjuntos (evidencias, facturas escaneadas) se almacenan en el filestore de Odoo. Deben respaldarse también.

## Siguiente paso

> Continúa con [Solución de problemas y FAQ](./12-solucion-problemas-faq.md).
