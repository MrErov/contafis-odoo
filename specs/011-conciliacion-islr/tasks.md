# Tasks — Spec 011 Conciliación ISLR

Plan: `specs/011-conciliacion-islr/plan.md`. Spec: `specs/011-conciliacion-islr/spec.md`.

- [x] **T1. Crear modelos `l10n.ve.islr.reconciliation` y `.line`** (campos base, categorías, trazabilidad, estado, campos xlsx de referencia, PDF adjunto; import en `models/__init__.py`; ACL y reglas de compañía/cartera). RF-6, RF-13.
  Hecho cuando: `-u l10n_ve_compliance_manager` pasa sin errores, los modelos existen en shell, los 258 tests existentes siguen verdes.

- [x] **T2. Versionar fixture y crear parser puro** (`sanitize_rif`, `normalize_label`, `to_amount`, `RUBRO_MAP`, `parse_conciliacion_xlsx` en `models/islr_conciliation.py`; quitar fixture de `.gitignore` línea 45 y del `exclude` de `.pre-commit-config.yaml`). RF-1, RF-3, RF-4, RF-5, RF-15, RF-16.
  Hecho cuando: test del parser sobre el fixture real pasa (hoja case-insensitive, año 2025, RIF `J-99999999-0`, rubros del bloque principal, F45=47863.69, bloques laterales ignorados) y `git status` muestra el fixture listo para commit.

- [x] **T3. Computes de totales + advertencias + `warning_html`** (RF-7 a RF-11, RF-17). RF-7, RF-8, RF-9, RF-10, RF-11, RF-17.
  Hecho cuando: tests verdes — totales del fixture (mercancía 1982288.76, costo venta 1383802.26, renta bruta 607476.54 contabilidad), warning `descuadre` (deducciones recalc ≠ 184979.44), warning `monto` (34% × utilidad fiscal ≠ 47863.69), sintéticos de identidad/tope/base cero, y `warning_html` persistido y recalculado al editar.

- [x] **T4. Wizard: tipo "Conciliación ISLR" + carga con detección estricta** (`IMPORT_TYPES`, campos detectados, `_load_islr_conciliation_file`, preview con cliente/año/rubros; errores: RIF inexistente, RIF en dos compañías). RF-1, RF-3.
  Hecho cuando: test carga el fixture y expone cliente/año/nº rubros; tests de RIF inexistente y de ambigüedad multi-compañía lanzan `UserError` con mensaje claro.

- [x] **T5. Wizard: importación, reemplazo y trazabilidad** (`_import_islr_conciliation`, crear/reemplazar registro y líneas, checkbox de confirmación de reemplazo, aviso si cambió el RIF). RF-2, RF-6.
  Hecho cuando: test reimportar sin confirmar → `UserError`; con confirmar → reemplaza sin duplicar líneas y `modified_by/at` quedan registrados.

- [ ] **T6. Vistas lista/form + acción + menú** ("Conciliación ISLR" bajo "Cumplimiento VE", sequence 42, con bloque de advertencias y pestañas). RF-13.
  Hecho cuando: `load_menus` del admin incluye "Conciliación ISLR" con su acción y `get_views` carga lista y formulario sin errores de validación XML.

- [ ] **T7. Reporte QWeb + ciclo de vida validar/revertir** (`report/islr_conciliation_report.xml` réplica del bloque principal; `action_validate` genera y adjunta PDF; editar un registro validado lo devuelve a `draft` y elimina el PDF; botón Imprimir). RF-12, RF-14.
  Hecho cuando: al validar existe el attachment PDF con páginas > 0; editar una línea validada deja `state='draft'` y sin attachment; los 258 tests previos siguen verdes.

- [ ] **T8. Cerrar spec: regresión completa, SPEC.md y commit** (correr suite completa; marcar HECHO `SPEC.md` líneas 259/265; actualizar `docs/memory.md`; commit + push + CI). Todas.
  Hecho cuando: Odoo reporta `0 failed, 0 error(s) of N tests` con N = 258 + nuevos ≥ 259, `SPEC.md` refleja la spec 011 como HECHA, commit convencional pusheado y CI 3/3 verde.
