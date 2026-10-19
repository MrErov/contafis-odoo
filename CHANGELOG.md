# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

## [Unreleased]

### Añadido

- Guía de usuario: capítulo "Bandeja y análisis" (registrar pago, alerta manual,
  acciones masivas y vistas de análisis de obligaciones y alertas).

### Cambiado

- Guía de usuario: portada rediseñada con logo y versión, numeración de capítulos
  (01-13), tipografía de impresión y PDF de 58 páginas; "Exportar y respaldar
  datos" pasa a capítulo 12 y "Solución de problemas y FAQ" a 13.
- Tests: helper `_get_or_create_tax_group` unificado en `tests/common.py`
  (7 archivos de test).

### Corregido

- Instalación limpia: `obligation_analysis_views.xml` ahora se carga después de
  `menu.xml` en el manifest (el orden anterior rompía `-i` en CI).

## [1.2.0] - 2026-10-18

### Añadido

- Bandeja "Próximos vencimientos" accionable (spec 005): botones por fila y en el
  formulario para "Registrar pago" (wizard con fecha, referencia y comprobante) y
  "Crear alerta" (alerta `manual` a demanda con deduplicación contra
  pendientes/enviadas y link `wa.me` por el flujo existente).
- Marcado de pago y reapertura: `action_mark_paid` / `action_reopen` (fecha de pago
  automática, comprobante conservado al reabrir) y acciones masivas "Marcar pagadas
  (hoy)" / "Reabrir seleccionadas" sobre la selección de la bandeja.
- Menú "Análisis" con vistas graph/pivot nativas de obligaciones (estado, tipo,
  cliente, período, mes de vencimiento; medidas cantidad y monto) y de alertas
  (estado, canal, tipo).
- Calendario SENIAT 2026 en base de datos (tablas a.1/a.2 + días por último
  dígito del RIF), feriados bancarios con corrimiento a día hábil, generación
  automática de obligaciones y alertas `calendar_missing` (spec 003).
- Tablas de ISLR 2026 (estimadas `est_islr` y retenciones `ret_islr`) con
  vencimiento por último dígito del RIF sin gate SPE, generación de estimadas
  en jun/sep/dic y retenciones mensuales (spec 004).
- Identidad de la app: ícono 512px, descripción estática y `web_icon` del menú;
  README con hero, capturas y sección de capacidades.

### Corregido

- Hardening ISLR post-code-review (Fase 004.1): `_quincena_table_code` ya no
  remapea tablas ISLR, `@api.constrains` para la combinación quincenal + tabla
  ISLR y `generation_months`, índice de idempotencia del cron y tests de
  generación congelados con `freeze_time`.
- Auditoría post-spec-004: migración de `_sql_constraints` a `models.Constraint`
  (`vat.return`), `search` del campo `cartelera_status_current_ids`, menú faltante
  de "Libro de Compras/Ventas" y RIF vacío en exports XLSX.
- Wizard de factura física: etiquetas ambiguas renombradas y sección "nuevo
  partner" junto a identificación; locator E2E del título del modal corregido.

## [1.1.0] - 2026-10-17

### Añadido

- Wizard de importación Excel (obligaciones, documentos, clientes, retenciones)
  con validación referencial y de negocio en 3 niveles, upsert idempotente con
  savepoints y plantillas descargables (fases 2A-2B).
- Cartelera fiscal desde Excel: 36 tipos de documento (C01-C36), snapshots
  mensuales `cartelera.status`, vista de brechas, parser dinámico de cabeceras y
  evidencias fotográficas con compresión automática y límite configurable
  (fases A-E2).
- Libro de Compras/Ventas + Planilla IVA 99030 (48 ítems), importación desde
  Excel, export bidireccional y arrastre de excedente ítem 60 → ítem 20 del mes
  siguiente (fases F, G y G.10).
- Backend Odoo-First (spec 001): wizard de factura física, sincronización
  `account.move` → `vat.book.line` en `_post`, botón "Regenerar Libro", campos de
  auditoría en el libro, `l10n_ve_tax_type` (account.tax) y
  `l10n_ve_control_number` (account.move).
- E2E con Playwright (smoke, wizard de factura física, regenerar libro) e
  integración en GitHub Actions (fase H).
- Rediseño de vistas list/form/search de `l10n.ve.vat.return` y
  `l10n.ve.vat.book.line` (UX-1, UX-2).
- Guía de usuario en `docs/guia-usuario/`: portada, TOC navegable, callouts
  unificados y PDF de 50 páginas con capturas reales (fase I).
- Integración MCP Odoo (FGRibreau/mcp-odoo) para operar una instancia desde
  OpenCode Desktop (spec 002; herramienta de desarrollo).

### Corregido

- Separación de base nacional vs importación en `vat.book.line` (op_code 31) y
  suma del ítem 35 solo sobre bases (Bug-Fix Base-Import).
- Fixes descubiertos por E2E: `invisible` con tupla → lista en la vista
  `account.move`, 5 impuestos SENIAT faltantes y menú del wizard de factura
  física inexistente.
- `mail.template` de alertas (mezcla QWeb/inline_template que rompía `-u` al
  existir alertas) y `get_wa_url()` usando `res.partner.mobile` (removido en
  Odoo 19).

### Metodología

- Pre-commit con 7 hooks + ruff (E/W/F/I/UP) y `pyproject.toml` (DevOps.1);
  limpieza de 56 issues residuales (DevOps.1c).
- CI en GitHub Actions con jobs de lint, tests backend y E2E.

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
