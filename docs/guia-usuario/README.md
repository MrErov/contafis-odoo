# Guía de usuario — l10n_ve_compliance_manager

Guía paso a paso para contadores que administran múltiples
clientes en Venezuela con Odoo 19 Community.

## Contenido

1. [Introducción](./01-introduccion.md)
2. [Primeros pasos](./02-primeros-pasos.md)
3. [Gestión de clientes](./03-gestion-clientes.md)
4. [Cargar facturas físicas](./04-cargar-facturas.md)
5. [Libro de Compras y Ventas](./05-libro-compras-ventas.md)
6. [Planilla IVA 99030](./06-planilla-iva-99030.md)
7. [Retenciones](./07-retenciones.md)
8. [Calendario SENIAT](./08-calendario-seniat.md)
9. [Cartelera fiscal](./09-cartelera-fiscal.md)
10. [Alertas](./10-alertas.md)
11. [Exportar y respaldar datos](./11-exportar-respaldos.md)
12. [Solución de problemas y FAQ](./12-solucion-problemas-faq.md)

## Anexos

- [Glosario](./anexo-glosario.md)
- [Limitaciones conocidas](./anexo-limitaciones.md)

## Cómo regenerar la guía

    # 1. Capturar screenshots (requiere Odoo corriendo en localhost:8090)
    npm run capture:screenshots

    # 2. Generar el PDF
    npm run build:guide

El PDF se genera en `docs/guia-usuario/guia-usuario.pdf`.
