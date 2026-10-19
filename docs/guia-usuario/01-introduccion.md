# Introducción

## ¿Qué es esta guía?

Esta guía cubre el uso diario del módulo **l10n_ve_compliance_manager** en Odoo 19 Community. Está dirigida a contadores que administran múltiples clientes desde una sola instancia. No cubre la instalación del sistema ni la configuración técnica del servidor.

## ¿Para quién es?

- Contadores independientes con múltiples clientes
- Firmas contables pequeñas (2-5 contadores)
- Administradores que apoyan al contador

## ¿Qué problema resuelve?

El escenario típico: múltiples clientes, información dispersa en hojas de cálculo, riesgo de error manual en planillas fiscales y olvido de vencimientos SENIAT. El módulo centraliza la información de cada cliente y automatiza la generación de libros, planillas y alertas.

## Flujo general de uso

El ciclo mensual sigue estos pasos:

```
┌─────────────────────────────────────────┐
│  1. Registrar facturas de cada cliente  │
│     (foto, talonario, máquina fiscal)   │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  2. Revisar el libro de Compras/Ventas  │
│     del mes (auto-generado)             │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  3. Exportar Planilla IVA 99030         │
│     para cada cliente                   │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  4. Registrar retenciones IVA/ISLR      │
│     y enviar comprobantes               │
└─────────────────────────────────────────┘
```

## Requisitos previos

- Odoo 19 Community instalado y funcionando
- Módulo **l10n_ve_compliance_manager** instalado
- PostgreSQL 15+ (viene con Odoo)
- Navegador moderno (Chrome, Edge, Firefox)
- Cuenta de correo SMTP configurada (para alertas)
- Conexión a internet (WhatsApp vía `wa.me`)

## Convenciones de esta guía

- Los **campos del sistema** aparecen en negrita.
- Los botones aparecen [entre corchetes] como [Guardar].
- Las rutas de menú se muestran así: *Cumplimiento VE → Factura Física Rápida*.
- Los bloques de código o valores van en `monospace`.
- Las imágenes muestran la pantalla real del sistema con anotaciones en rojo (cuadros y números).

## Cómo usar esta guía

Puede leerla de corrido o consultar por sección. Cada sección es autocontenida. Los screenshots muestran la pantalla real del sistema con anotaciones que indican dónde hacer clic.

## Siguiente paso

> Si es la primera vez que usa el sistema, continúe con [Primeros pasos](./02-primeros-pasos.md). Si ya tiene la empresa y el usuario configurados, salte a [Gestión de clientes](./03-gestion-clientes.md).
