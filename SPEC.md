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
1. **[01-calendario-seniat.md](specs/01-calendario-seniat.md)** — Cálculo vencimientos SENIAT 2026 por dígito RIF + reglas genéricas
2. **[02-gestion-alertas.md](specs/02-gestion-alertas.md)** — Motor de alertas multi-canal (email + wa.me) + cron diario
3. **[03-cartelera-fiscal.md](specs/03-cartelera-fiscal.md)** — Documentos legales: vigencia, renovación, alertas expiración/faltantes
4. **[04-retenciones.md](specs/04-retenciones.md)** — Retenciones IVA/ISLR/IGTF en facturas proveedor + extensión account.move
5. **[05-dashboard-reportes.md](specs/05-dashboard-reportes.md)** — Dashboard contador (kanban semáforos, score, PDF)
6. **[06-importacion-excel.md](specs/06-importacion-excel.md)** — Wizard de
   importación masiva desde Excel (obligaciones, documentos, clientes,
   retenciones) con validación en 3 niveles y upsert
7. **[07-cartelera-excel.md](specs/07-cartelera-excel.md)** — Importación de la cartelera fiscal desde
     Excel mensual (36 documentos, snapshot por cliente/mes)
8. **[08-evidencias.md](specs/08-evidencias.md)** — Evidencia
   fotográfica de documentos de cartelera + transición
   automática de estado
9. **[09-libro-compras-ventas.md](specs/09-libro-compras-ventas.md)**
     — Libro de Compras/Ventas + Planilla IVA 99030
10. **[10-importacion-libro-compras-ventas.md](specs/10-importacion-libro-compras-ventas.md)**
     — Importación de Libro de Compras/Ventas desde Excel (canal
     alterno al Odoo-first)

## Modelos Principales (resumen)
- `l10n.ve.compliance.client` — Cliente multi-empresa, score, status, alertas
- `l10n.ve.institution` — SENIAT, IVSS, INCES, BANAVIH, municipales, SAREN
- `l10n.ve.obligation.type` — Configuración regla vencimiento, alertas, tasas
- `l10n.ve.obligation` — Instancia por período, due_date computed, estado, retención
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
- ✅ 121 tests (2 fallos pre-existentes en test_vat_book_generate)
- ✅ Commits: d75f1b8, d6cf23d, 7eb86bd, + marcas de Tn

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

### Trabajo Futuro
- ⬜ Spec 11: Conciliación ISLR
- ⬜ Fix 2 tests pre-existentes en test_vat_book_generate
- ⬜ post_init_hook: hacerlo efectivo con schema change (nullable source)
- ⬜ Migrar `_sql_constraints` a `models.Constraint`
- ⬜ Warning cartelera_status_current_ids no searchable
- ⬜ country_id guard en _post() para multi-país
- ⬜ Menú directo para vat.book.line list
- ⬜ Importación de asientos contables (account.move)
- ⬜ Integración MCP Odoo (mart337i/odoo-dev-mcp)
- ⬜ Fix RIF None en export XLSX cuando company.vat está vacío
- ⬜ DevOps.1b: ruff-format (opcional, reformatearía 30+ archivos)
- ⬜ DevOps.2: GitHub Actions CI (lint + test jobs)

## Estado del Portafolio

- ✅ README.md, CHANGELOG.md, LICENSE (LGPL-3), CONTRIBUTING.md
- ✅ Metodología SDD (AGENTS.md, docs/specs/, opencode.json)
- ✅ 107 tests pasando
- ✅ Ruff limpio en E/W/F/I/UP (nuevo)
- ✅ Pre-commit configurado con ruff (nuevo)
- ✅ Comandos OpenCode en `.opencode/commands/`
- ⬜ Capturas de pantalla en docs/screenshots/
- ⬜ Topics GitHub
