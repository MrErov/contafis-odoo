# Proyecto: l10n_ve_compliance_manager
Módulo Odoo 19.0 para gestión de cumplimiento fiscal, parafiscal y documental
para contadores en Venezuela. Multi-cliente (el contador gestiona varias empresas).

## Stack
- Odoo 19.0 Community
- Python 3.10+, PostgreSQL 14+
- Dependencias: base, account, mail, l10n_ve

## Convenciones Odoo 19 (OBLIGATORIO)
- Usar `<list>` NO `<tree>`
- Usar `invisible="campo != 'valor'"` NO `states`
- `view_mode="list,form"`
- Sin `expand=` en search views
- Seguir API Odoo 19 (no usar `attrs=`)

## Índice de Especificaciones por Capacidad (SDD)
1. **[01-calendario-seniat.md](docs/capacidades/01-calendario-seniat.md)** — Cálculo vencimientos SENIAT 2026 por dígito RIF + reglas genéricas
2. **[02-gestion-alertas.md](docs/capacidades/02-gestion-alertas.md)** — Motor de alertas multi-canal (email + wa.me) + cron diario
3. **[03-cartelera-fiscal.md](docs/capacidades/03-cartelera-fiscal.md)** — Documentos legales: vigencia, renovación, alertas expiración/faltantes
4. **[04-retenciones.md](docs/capacidades/04-retenciones.md)** — Retenciones IVA/ISLR/IGTF en facturas proveedor + extensión account.move
5. **[05-dashboard-reportes.md](docs/capacidades/05-dashboard-reportes.md)** — Dashboard contador (kanban semáforos, score, PDF)
6. **[06-importacion-excel.md](docs/capacidades/06-importacion-excel.md)** — Wizard de
   importación masiva desde Excel (obligaciones, documentos, clientes,
   retenciones) con validación en 3 niveles y upsert
7. **[07-cartelera-excel.md](docs/capacidades/07-cartelera-excel.md)** — Importación de la cartelera fiscal desde
   Excel mensual (36 documentos, snapshot por cliente/mes)
8. **[08-evidencias.md](docs/capacidades/08-evidencias.md)** — Evidencia
   fotográfica de documentos de cartelera + transición
   automática de estado
9. **[09-libro-compras-ventas.md](docs/capacidades/09-libro-compras-ventas.md)**
   — Libro de Compras/Ventas + Planilla IVA 99030
10. **[10-importacion-libro-compras-ventas.md](docs/capacidades/10-importacion-libro-compras-ventas.md)**
    — Importación de Libro de Compras/Ventas desde Excel (canal
    alterno al Odoo-first)

## Modelos Principales (resumen)
- `l10n.ve.compliance.client` — Cliente multi-empresa, score, status, alertas
- `l10n.ve.institution` — SENIAT, IVSS, INCES, BANAVIH, municipales, SAREN
- `l10n.ve.obligation.type` — Configuración regla vencimiento, alertas, tasas
- `l10n.ve.obligation` — Instancia por período, due_date computed, estado, retención
- `l10n.ve.seniat.calendar.table` — Tabla SENIAT por año/código (a.1/a.2/est_islr/ret_islr); 2026 precargada
- `l10n.ve.seniat.calendar` — Día de vencimiento por mes y último dígito del RIF
- `l10n.ve.bank.holiday` — Feriados bancarios (base del corrimiento a día hábil)
- `l10n.ve.copy.calendar.wizard` — Wizard "Copiar a otro año" del calendario SENIAT
- `l10n.ve.document.type` / `l10n.ve.document` — Cartelera fiscal
- `l10n.ve.alert` — Notificaciones multi-tipo, multi-canal
- `l10n.retention` — Comprobante retención (secuencia RET-YYYY-NNNN)
- `l10n.ve.import.wizard` / `l10n.ve.import.line` / `l10n.ve.import.mapping`
  / `l10n.ve.import.log` — Wizard de importación Excel (4 modelos)
- `l10n.ve.cartelera.status` — Snapshot mensual de cartelera fiscal
- `l10n.ve.cartelera.evidence` — Evidencia fotográfica con compresión automática
  y límite de tamaño configurable
- `l10n.ve.cartelera.evidence.wizard` — Captura/subida de evidencia al cliente
- `l10n.ve.vat.book.line` — Línea de libro de compras/ventas IVA
- `l10n.ve.vat.book.generate` — Wizard de generación desde account.move
- `l10n.ve.vat.return` — Planilla IVA 99030 (48 ítems fijos)
- `l10n.ve.islr.reconciliation` / `l10n.ve.islr.reconciliation.line` — Conciliación fiscal ISLR (import Excel con advertencias, validar → PDF)

## Extensiones Core
- `account.move`: `retention_ids`, `retention_amount`, `action_generate_retention()` (solo `in_invoice`)
- `res.partner`: `compliance_client_ids`, `compliance_status`, `document_ids`

## Roadmap

### Fases 1-7: Módulo base (COMPLETADAS)
1. ✅ Scaffold módulo + modelos + security
2. ✅ Vistas list/form/kanban de cada modelo
3. ✅ Cálculo de vencimientos + cron
4. ✅ Sistema de alertas (email + wa.me)
5. ✅ Dashboard contador + reportes PDF
6. ✅ Retenciones + account.move
7. ✅ Datos demo + tests

### Fase 2A-2B: Wizard de importación Excel (COMPLETADA)
- ✅ 2A: Parser de números VE + validación RIF módulo 11
- ✅ 2B.1: `_validate_reference` (validación referencial)
- ✅ 2B.2: `_validate_business` (validación de negocio)
- ✅ 2B.3: `action_import` + `_upsert_record` + savepoints

### Fase A-E: Cartelera Fiscal Excel (COMPLETADA)
- ✅ A: 36 tipos de documento (C01-C36) + institución MINTRA
- ✅ B: Modelo `cartelera.status` + `document_score`
- ✅ C: Parser + import (rama `cartelera` del wizard)
- ✅ D: Vista de brechas + spec 07 + tests
- ✅ E: Parser dinámico (detección fila headers, col RIF, col nombre, rango docs; mapeo posicional C01..C36; manejo duplicados; normalización HTML; validación 30+ cols; warning headers no reconocidos)

### Fase E2: UX visual cartelera fiscal (COMPLETADA)
- ✅ Evidence con compresión automática + límite de tamaño configurable
- ✅ Logo cliente en kanban
- ✅ Mini-cartelera HTML agrupada por institución
- ✅ Kanban extendido con document_score
- ✅ Fix OWL: kanban_image y t-out reemplazados por patrones Odoo 19
- ✅ 63 tests pasando

### Fase F: Libro de Compras/Ventas + Planilla IVA 99030 (COMPLETADA)
- ✅ Modelo l10n.ve.vat.book.line (multi-rate por factura)
- ✅ Wizard l10n.ve.vat.book.generate desde account.move
- ✅ Modelo l10n.ve.vat.return (48 ítems Forma 99030)
- ✅ Arrastre de excedente item_60 → item_20 mes siguiente
- ✅ Reporte PDF Forma 99030
- ✅ 78 tests pasando (63 + 15 nuevos)

### Fase G: Importación de Libro de Compras/Ventas desde Excel (COMPLETADA)
- ✅ Wizard con 3 import_types: vat_book_purchase, vat_book_sale,
  vat_book_both
- ✅ Parser dinámico con detección de headers por keywords
- ✅ Multi-rate por factura (una línea por tasa IVA distinta)
- ✅ Retención dividida (to_vendor / to_third / by_buyer)
- ✅ Upsert idempotente con constraint único de 7 campos
- ✅ 3 plantillas descargables (Compras, Ventas, Both con 2 hojas)
- ✅ 6 tests de integración con Excel real
- ✅ 96 tests pasando (90 + 6 nuevos)

### G.10: Export bidireccional (COMPLETADA)
- ✅ Export vat.book.line a Excel (round-trip con import)
- ✅ Export vat.return (Planilla 99030) a Excel
- ✅ Corrección de conceptos del PDF con nombres SENIAT literales
- ✅ 107 tests pasando (96 + 11 nuevos)

### Bug-Fix Base-Import (COMPLETADA)
- ✅ Separación de base nacional vs importación en vat.book.line
- ✅ Parser detecta importaciones como _rate_type='import'
- ✅ Mapeo a op_code '31' (importación SENIAT)
- ✅ action_load_from_book llena item_31/item_32
- ✅ Fix derivado: item_35 suma solo bases
- ✅ Commits: 5ef4224, 5a29e97

### Backend Odoo-First (spec 001) — COMPLETADA
- ✅ Wizard factura física (l10n.ve.physical.invoice.wizard)
- ✅ Sync automático account.move → vat.book.line (override _post)
- ✅ Botón "Regenerar Libro" + wizard de confirmación
- ✅ Campos auditoría en vat.book.line (source, modified_by, is_manually_modified)
- ✅ Refactor _get_operation_code() a vat_book_line.py
- ✅ Campos l10n_ve_tax_type (account.tax) + l10n_ve_control_number (account.move)
- ✅ ACLs + post_init_hook + export regression test
- ✅ Fix retention_direction en _post() y action_generate() (T5 sync)
- ✅ 121 tests pasando (fix tests pre-existentes)
- ✅ Commits: d75f1b8, d6cf23d, 7eb86bd, 972fe19, + marcas de Tn

### DevOps.1: Pre-commit hooks + ruff config (COMPLETADA)
- ✅ pyproject.toml con ruff (E/W/F/I/UP, line-length=120)
- ✅ .pre-commit-config.yaml con 7 hooks (trailing-whitespace, end-of-file-fixer, check-yaml, check-xml, check-added-large-files, mixed-line-ending, ruff)
- ✅ pylint-odoo comentado (sin release 19.x aún)
- ✅ Commit: 62b82e0

### DevOps.1c: Limpieza ruff (COMPLETADA)
- ✅ 56 issues residuales resueltos
- ✅ F601: dict key duplicada en import_wizard.action_reset
- ✅ E741: 25 lambdas `l` → `line` (5 archivos)
- ✅ UP038: 9 isinstance → union syntax (3 archivos)
- ✅ F841: 18 variables no usadas (9 archivos, 10 CONVERTIR por side effects, 8 ELIMINAR)
- ✅ UP031: 4 % format → f-strings (test_document_types.py)
- ✅ F401: importlib.util.find_spec para PIL opcional
- ✅ Commits: 06e2694, bba5bde, e5464da
- ✅ Ruff limpio en E/W/F/I/UP sobre todo el repo
- ✅ 107 tests pasando

### Fase H: E2E con Playwright (COMPLETADA — 7/7 sub-fases)
- ✅ Fase 0: Menú wizard + vista heredada
- ✅ Fase 1: Setup Playwright (package.json, playwright.config.js)
- ✅ Fase 2: Smoke test (login + navbar + console limpia) — 3 tests
- ✅ Fase 3: Wizard factura física (abrir, validar RIF, submit) — 3 tests
- ✅ Fase 4: Regenerar libro (botón + click sin error) — 1 test
- ✅ Fase 5: Planilla IVA + líneas del libro E2E — 1 test (crear desde libro, calcular, exportar XLSX)
- ✅ Fase 6: Multi-company E2E — 1 test (aislamiento de clientes/obligaciones al cambiar de compañía; reglas `ir.rule` globales por compañía + 6 tests backend)
- ✅ Fase 7: CI integration (GitHub Actions) — job e2e-tests en .github/workflows/ci.yml

### Fixes descubiertos por E2E
- Vista account.move: `invisible` con tupla → lista (commit 004afcd)
- Faltaban 5 SENIAT VAT taxes (commit 781ee07)
- Menú wizard factura física no existía (commit 718f0be)
- Tests wizard: menús en español + waitForSelector navbar (commit e57748a)

### Estado actual
- 9/9 tests E2E pasando
- 258/258 tests backend pasando
- Total: 267 tests
- CI: 3/3 jobs verdes (lint + backend-tests + e2e-tests)

### UX-1: Rediseño vistas vat.return (COMPLETADA)
- ✅ List view: columnas ordenadas, badges, sumatorias, totales
- ✅ Form view: grupos lógicos, readonly, readonly no editable
- ✅ Search view: filtros por estado, período, cliente, group by
- ✅ Commit: 4239263

### UX-2: Rediseño vistas vat.book.line (COMPLETADA)
- ✅ List view: badge book_type, sumatorias por columna, optional=hide
- ✅ Form view: 3 grupos (Identificación, Bases e IVA, Retenciones), create=false
- ✅ Search view: campos + 4 filtros (Compras, Ventas, Con Retención, Con Importación) + 4 group by
- ✅ Commit: 729f0f4

### Fase I: Guía de usuario (COMPLETADA)
- ✅ Portada + TOC navegable (anclas de h1/h2) generados en `scripts/build-guide.js`
- ✅ CSS de callouts unificados (`.step/.expected/.warning/.tip/.note/.troubleshoot`) en `guide.css`
- ✅ Capturas reales vía `scripts/capture-screenshots.js` (wizards abiertos client-side
  sobre la app Cumplimiento VE, no sobre la app por defecto)
- ✅ `seedDemoData()` idempotente: 3 clientes, documentos, 108 snapshots de
  cartelera, 2 planillas, 4 alertas (desactivable con `SKIP_SEED=1`)
- ✅ PDF final `docs/guia-usuario/guia-usuario.pdf` (68 páginas, ~5.4 MB)
- ✅ Rediseño 2026-10: portada con logo y versión, numeración de capítulos (01-13 + anexos 14-15),
  tipografía de impresión y capítulo "Bandeja y análisis" (spec 005)
- ✅ Fix bug de producción: `mail.template` mezclaba sintaxis QWeb e
  inline_template y rompía `-u` al existir ≥1 alerta (Odoo 19 valida los
  templates renderizándolos contra el primer registro del modelo)
- ✅ Fix bug de producción: `l10n.ve.alert.get_wa_url()` usaba
  `res.partner.mobile` (removido en Odoo 19)
- ✅ 121 tests pasando

### MCP Odoo (integración OpenCode Desktop) — COMPLETADA
- ✅ Server MCP `FGRibreau/mcp-odoo` v0.2.1 (binario Rust, stdio) — spec 002
- ✅ API key JSON/2 (Bearer) generada en odoo shell y persistida en env var
  de usuario (nunca en el repo)
- ✅ Config global en `~/.config/opencode/opencode.jsonc`: `ODOO_URL=127.0.0.1:8090`,
  `ODOO_DB=contea`, `ODOO_PROTOCOL=json2`, `MODEL_INCLUDE=l10n.ve.*,account.*,res.*,product.*,uom.uom`
- ✅ 8 tools: `list_models`, `describe_model`, `search`, `read`, `create`, `write`,
  `delete`, `call_method`
- ✅ Smoke test E2E: crear partner → factura compra (línea + IVA 16%) → post →
  línea del libro 6→7 → rename → borrador → libro 7→6 → delete (verificado con psql)
- ✅ Anomalía de concurrencia documentada (paralelismo `tokio::join!` + relay
  Docker Desktop) con workaround vía `call_method` secuencial
- ✅ Artefactos: `specs/002-mcp-odoo/{spec,plan,tasks}.md` + sección "MCP Odoo" en `AGENTS.md`
- ✅ 121 tests pasando

### Fase 003: Calendario SENIAT (spec 003) — COMPLETADA
- ✅ Modelos `l10n.ve.seniat.calendar.table`/`l10n.ve.seniat.calendar` (`models.Constraint`) + precarga 2026 a.1/a.2 (240 líneas, `noupdate="1"`)
- ✅ `l10n.ve.bank.holiday` + 13 feriados nacionales 2026; corrimiento a día hábil bancario
- ✅ Cálculo de `due_date`: quincenas SPE por tabla (último dígito RIF), no-SPE día 15, `1-15` legacy vía a.1, `dia_fijo`
- ✅ `_cron_generate_obligations` (ventana mes actual + próximo, idempotente), botón "Generar obligaciones" y alerta `calendar_missing`
- ✅ Alertas al contador (`accountant_id`, CC opcional, email + `wa.me`) y seguridad por contador (`security/ir_rule.xml`)
- ✅ Bandeja "Próximos vencimientos" (filtro 30 días) y wizard "Copiar a otro año"
- ✅ Demo data SPE/no-SPE + test de integración end-to-end (`TestCalendarIntegration`)
- ✅ 193 tests pasando; tareas T1–T10 `[x]` en `specs/003-calendario-seniat/tasks.md`

### Fase 004: Tablas de ISLR — Estimadas y Retenciones (spec 004) — COMPLETADA
- ✅ Precarga 2026 `est_islr` (30 líneas: jun/sep/dic × 10 dígitos, sin corrimiento) y `ret_islr` (120 líneas: 12 meses × 10 dígitos, vence el mes siguiente), `noupdate="1"` y marcadas como referencia sujeta a verificación con la Gaceta
- ✅ Tipos "Estimadas de ISLR" (`generation_months="6,9,12"`) y "Retenciones de ISLR" (`tax_type=islr`), editables y asignables por cliente
- ✅ Vencimiento por último dígito del RIF sin gate `is_spe` (día = dígito + 10) con corrimiento a día hábil; alerta `calendar_missing` si el año no tiene tabla
- ✅ Generación automática: estimadas jun/sep/dic, retenciones mensuales; idempotente; reutiliza el flujo de alertas existente
- ✅ Wizard "Copiar a otro año" incluye est_islr/ret_islr (RF-14); demo + verificación visual (T6)
- ✅ 217 tests pasando; tareas T1–T7 `[x]` en `specs/004-tablas-islr/tasks.md`

### Fase 004.1: Hardening ISLR (Post-Code Review) — COMPLETADA
- ✅ `_quincena_table_code` ya no remapea `est_islr`/`ret_islr` a a1/a2 en tipos quincenales: el vencimiento ISLR resuelve siempre por su propia tabla
- ✅ `@api.constrains` en el tipo de obligación: prohíbe la combinación quincenal + tabla ISLR y valida `generation_months` (estrictamente comas, meses 1-12)
- ✅ Índice `_client_type_period_idx` en `l10n.ve.obligation` para la búsqueda de idempotencia del cron
- ✅ Tests de generación congelados con `odoo.tests.freeze_time` (`2026-10-15`): la ventana del cron queda dentro de las tablas 2026 y se elimina el time-bomb de diciembre 2026
- ✅ 222 tests pasando (217 + 5 nuevos de constraints y mapeo)

### Fase 005: Bandeja de vencimientos accionable + Análisis (spec 005) — COMPLETADA
- ✅ Acciones de modelo `action_mark_paid` / `action_reopen` (fecha de pago automática, comprobante conservado al reabrir)
- ✅ Wizard "Registrar pago" desde la fila de la bandeja y el formulario (fecha, referencia, comprobante adjunto)
- ✅ Alerta manual a demanda (`alert_type=manual`) con deduplicación contra pendientes/enviadas y link `wa.me` por el flujo existente
- ✅ Acciones masivas "Marcar pagadas (hoy)" / "Reabrir seleccionadas" (server actions ligadas a la lista)
- ✅ Menú "Análisis" con vistas graph + pivot de obligaciones y alertas
- ✅ 245 tests pasando; tareas T1–T5 `[x]` en `specs/005-bandeja-acciones-kpis/tasks.md`

### Fase 011: Conciliación ISLR (spec 011) — COMPLETADA
- ✅ Modelos `l10n.ve.islr.reconciliation` y `l10n.ve.islr.reconciliation.line`: 10 rubros (ingresos/costos/deducciones), identidad contab = fiscal + no deducible (tolerancia 0.01) y constraint único cliente + compañía + año
- ✅ Wizard "Importar desde Excel": parser de la hoja CONCILIACIÓN (case-insensitive, bloque B12:F46), RIF sanitizado con desambiguación por compañía, duplicados y celdas de texto reportadas, totales y monto a pagar recalculados del lado del sistema
- ✅ Advertencias de descuadre (contabilidad/fiscal) y regla del 10% sobre sueldos directivos; monto calculado = 34% × utilidad neta fiscal (vs. monto informado en el Excel)
- ✅ Ciclo de vida: Validar (borrador → validada + PDF adjunto "Conciliación ISLR - {name}.pdf"), Revertir a borrador (desvincula el PDF) y escritura bloqueada en validadas
- ✅ Reporte QWeb `islr_conciliation_report` con sección de advertencias y columna "Preceptos Legales"; botón Imprimir visible solo en validadas
- ✅ Demo data: cliente "Comercial La Conciliación, C.A." (RIF J-30512345-6) + conciliación 2025 réplica del fixture real, con advertencias intencionales (totales y monto no cuadran por diseño)
- ✅ 330 tests backend + 9 E2E = 339 tests pasando; tareas T1–T8 `[x]` en `specs/011-conciliacion-islr/tasks.md`

### Trabajo Futuro
- ✅ Hardening 004.1 — Minor 1: recalcular `due_date` al cambiar el tipo o el cliente salvo en obligaciones pagadas — HECHO (decisión: recalc si no está pagada; incluye la acción manual "Recalcular vencimientos" en el formulario y como acción masiva de la lista, respetando `due_date_override`)
- ✅ Spec 11: Conciliación ISLR — HECHO (Fase 011: modelos + wizard + ciclo de vida + reporte QWeb + demo)
- ✅ Precargar tablas ISLR (est_islr/ret_islr) del calendario SENIAT 2026 — HECHO (spec 004)
- ✅ Fase H: E2E con Playwright — 7/7 sub-fases completadas (0-7); Fases 5-6 cerradas junto con las reglas de aislamiento multi-compañía
- ✅ Fixture real de cartelera versionado (`Control_Cartelera_Fiscal_Prueba.xlsx`) + test de parseo de la hoja enero (`test_parse_real_cartelera_fixture_enero`); la detección amplía el bloque de documentos al mínimo esperado porque en el archivo real el label "Total" cae sobre la columna de C36
- ✅ Cartelera: detección de columna RIF en meses ≠ enero — HECHO (sniffing del patrón RIF V/E/J/P/G sobre las filas de datos; feb/dic reales parsean 10 empresas × 36 estatus; tests unitarios sintéticos + `test_parse_real_cartelera_fixture_febrero`)
- ⬜ Cartelera: la hoja diciembre del fixture real trae 43 columnas y un header extra "Registro y elemento publicitario" (queda en `unmatched_headers`, benigno) — decidir si ignorarlo silenciosamente
- ✅ Test de integración con fixture de conciliación fiscal — HECHO: `CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx` versionado en `tests/fixtures/` (spec 011)
- ✅ post_init_hook: cerrado como descartado — no-op defensivo por diseño (`source` nace con `default='manual'`, nunca hay NULLs); hacerlo efectivo requeriría esquema nullable y sobrescribiría datos legítimos. Limitación documentada en el docstring
- ✅ Migrar `_sql_constraints` a `models.Constraint` — HECHO (último: `vat_return.py` → `_unique_return`)
- ✅ Warning cartelera_status_current_ids no searchable — HECHO (`search='_search_cartelera_status_current_ids'`)
- ✅ country_id guard en `_post()` para multi-país — HECHO (solo compañías con `account_fiscal_country_id` VE generan líneas del libro)
- ✅ Menú directo para vat.book.line list — HECHO (`menu_l10n_ve_vat_book_line`, sequence 65)
- ⬜ Importación de asientos contables (account.move)
- ✅ Fix RIF None en export XLSX cuando company.vat está vacío — HECHO (`vat_return.py` y `vat_book_export_wizard.py` ya usan `vat or ''`)
- ⬜ DevOps.1b: ruff-format (opcional, reformatearía 30+ archivos)
- ✅ DevOps.2: GitHub Actions CI (lint + test jobs) — HECHO (B3-e2e-ci)

### Deuda Técnica
- ✅ Helper `_get_or_create_tax_group()` duplicado en 7 test files — extraído a `tests/common.py` (mixin `TaxGroupMixin`)

## Estado del Portafolio

- ✅ README.md, CHANGELOG.md, LICENSE (LGPL-3), CONTRIBUTING.md
- ✅ Metodología SDD (AGENTS.md, docs/capacidades/, opencode.json)
- ✅ 330 tests backend + 9 tests E2E = 339 tests pasando
- ✅ Ruff limpio en E/W/F/I/UP
- ✅ Pre-commit configurado con ruff
- ✅ Comandos OpenCode en `.opencode/commands/`
- ✅ Integración MCP Odoo (FGRibreau/mcp-odoo v0.2.1) para operar `contea` desde OpenCode Desktop
- ✅ Guía de usuario en `docs/guia-usuario/`: portada, TOC, capturas reales y PDF (68 páginas)
- ⬜ Topics GitHub
