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
8. [Calendario SENIAT e ISLR](./08-calendario-seniat.md)
9. [Cartelera fiscal](./09-cartelera-fiscal.md)
10. [Alertas](./10-alertas.md)
11. [Bandeja, análisis y Asistente IA](./11-bandeja-acciones-analisis.md)
12. [Exportar y respaldar datos](./12-exportar-respaldos.md)
13. [Digitalización de facturas (IA Vision)](./14-digitalizacion-facturas.md)
14. [Solución de problemas y FAQ](./13-solucion-problemas-faq.md)

## Anexos

- [Glosario](./anexo-glosario.md)
- [Limitaciones conocidas](./anexo-limitaciones.md)

## Cómo regenerar la guía

    # 1. Capturar screenshots (requiere Odoo corriendo en localhost:8090)
    npm run capture:screenshots

    # 2. Generar el PDF
    npm run build:guide

El PDF se genera en `docs/guia-usuario/guia-usuario.pdf`.

## Screenshots nuevos requeridos (Spec 006 / 007)

| Archivo | Descripción | Capítulo |
|---------|-------------|----------|
| `11-07-chat-asistente.png` | Chat Discuss abierto con ContaFis AI y una respuesta visible | 11 |
| `14-01-wizard-digitalizar.png` | Wizard de digitalización - pantalla inicial con formulario vacío | 14 |
| `14-02-resultado-verde.png` | Resultado de digitalización con confianza verde (≥0.85) y warnings | 14 |
| `14-03-boton-usar-datos.png` | Botón "Usar datos en Factura Física Rápida" habilitado | 14 |

> **Nota:** Ejecute `npm run capture:screenshots` después de tener Odoo corriendo y el asistente fiscal accesible. El script de Playwright navegará y capturará cada pantalla automáticamente.
