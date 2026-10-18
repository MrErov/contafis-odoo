# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

## [Unreleased]

### Añadido

- Calendario SENIAT 2026 en base de datos (tablas a.1/a.2 + días por último
  dígito del RIF), feriados bancarios con corrimiento a día hábil, generación
  automática de obligaciones y alertas `calendar_missing` (spec 003).
- Tablas de ISLR 2026 (estimadas `est_islr` y retenciones `ret_islr`) con
  vencimiento por último dígito del RIF sin gate SPE, generación de estimadas
  en jun/sep/dic y retenciones mensuales (spec 004).

### Corregido

- Hardening ISLR post-code-review (Fase 004.1): `_quincena_table_code` ya no
  remapea tablas ISLR, `@api.constrains` para la combinación quincenal + tabla
  ISLR y `generation_months`, índice de idempotencia del cron y tests de
  generación congelados con `freeze_time`.

## [1.0.0] - 2026-09-26

### Añadido

- Modelo `l10n.ve.compliance.client` para gestión multi-cliente.
- Modelo `l10n.ve.institution` con catálogo de instituciones venezolanas.
- Modelo `l10n.ve.obligation.type` como catálogo maestro de obligaciones.
- Modelo `l10n.ve.obligation` con cálculo automático de fecha de vencimiento.
- Modelo `l10n.ve.document.type` y `l10n.ve.document` para cartelera fiscal.
- Modelo `l10n.ve.alert` con envío por email y WhatsApp (`wa.me`).
- Modelo `l10n.retention` vinculado a facturas de proveedor.
- Extensión de `account.move` con `retention_ids`, `retention_amount` y
  `action_generate_retention()`.
- Extensión de `res.partner` con estado de cumplimiento y documentos.
- Calendario SENIAT 2026 conforme a Providencia SNAT/2025/000091.
- Cron diario para generación automática de alertas.
- Plantillas de email multi-idioma para alertas de cumplimiento.
- Vistas list, form, kanban y search para todos los modelos.
- Dashboard del contador con puntuación de cumplimiento (0–100).
- Reporte PDF "Estado de Cumplimiento por Cliente".
- Seguridad por grupos: `account.group_account_user`,
  `account.group_account_manager` y `l10n_ve_compliance_accountant`.
- Pruebas unitarias con `TransactionCase` (5 escenarios).
- Setup Docker Compose con Odoo 19.0 y PostgreSQL 14.

### Metodología

- Spec-Driven Development (SDD) con `SPEC.md`, `AGENTS.md` y `docs/capacidades/`.
- Subagente IA `odoo19-dev` configurado en `opencode.json`.
- Skill propio `calcular-retencion-venezuela` para lógica de retenciones.

### Convenciones técnicas

- Odoo 19.0: uso de `<list>` en lugar de `<tree>`,
  `invisible="campo != 'valor'"`, sin `attrs=` ni `states=`.
- Compatible con Odoo 19.0 Community.
