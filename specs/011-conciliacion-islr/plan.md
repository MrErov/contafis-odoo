# Plan técnico — Spec 011 Conciliación ISLR

Referencia: `specs/011-conciliacion-islr/spec.md` (aprobada 2026-10-19). RF-1 a RF-17.

## 1. Archivos

### Nuevos
| Archivo | Responsabilidad |
|---|---|
| `models/islr_conciliation.py` | Modelos `l10n.ve.islr.reconciliation` y `l10n.ve.islr.reconciliation.line`: campos, computes de totales (contabilidad/fiscal), `_collect_warnings()`, `warning_html` computed-stored, `action_validate()` (estado + PDF adjunto), reversión a borrador al editar, trazabilidad `modified_by/at` (patrón `vat.book.line`). Helpers puros a nivel de módulo: `sanitize_rif()`, `normalize_label()`, `parse_conciliacion_xlsx()`, `to_amount()`, constante `RUBRO_MAP`. |
| `views/islr_conciliation_views.xml` | Lista (año, estado, cliente, moneda de totales) + formulario (botones Validar / Imprimir PDF, state widget, bloque HTML de advertencias, pestañas Rubros (editable inline) / Totales (read-only) / Referencia Excel) + acción + menú "Conciliación ISLR" bajo "Cumplimiento VE" (sequence 42). |
| `report/islr_conciliation_report.xml` | `ir.actions.report` qweb-pdf + template que replica el bloque principal: rubros agrupados por categoría con columnas Contabilidad / Fiscal / No deducible + Precepto, totales (contabilidad y fiscal), monto a pagar calculado vs informado, advertencias al pie. Patrón de `report/vat_return_report.xml`. |
| `tests/test_islr_conciliation.py` | Clases de parse (fixture real), compute, warnings, ciclo de vida (reimportar/validar/revertir) y errores estrictos. |

### Modificados
| Archivo | Cambio |
|---|---|
| `models/import_wizard.py` | Nuevo tipo `islr_conciliation` ("Conciliación ISLR") en `IMPORT_TYPES`; rama en `action_load_file()` → `_load_islr_conciliation_file()`; rama en `action_import()` → `_import_islr_conciliation()`; campos detectados (`conciliacion_client_id`, `conciliacion_year`, `conciliacion_existing_id`, `replace_confirmed` Boolean, contador de rubros); `action_download_template` no aplica (guard). |
| `models/__init__.py` | Import de `islr_conciliation`. |
| `__manifest__.py` | Datos: `views/islr_conciliation_views.xml`, `report/islr_conciliation_report.xml`. |
| `security/ir.model.access.csv` | ACL para ambos modelos: `account.group_account_user` (lectura), `account.group_account_manager` (CRUD), `l10n_ve_compliance_accountant` (CRUD) — patrón `vat.return`. |
| `security/ir_rule.xml` | Regla por compañía (`company_id in company_ids`) + regla cartera (`client_id.accountant_id = user.id`) patrón obligación. |
| `tests/__init__.py` | Import de `test_islr_conciliation`. |
| `.gitignore` | Quitar la línea 45 (`CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx`) para versionar el fixture. |
| `.pre-commit-config.yaml` | Añadir el fixture al `exclude` de `check-added-large-files`. |
| `SPEC.md` | Al cierre: marcar HECHO los ⬜ de líneas 259/265 y actualizar conteos. |
| `docs/memory.md` | Bitácora de decisiones y aprendizajes (local, no se commitea). |

## 2. Funciones puras (a nivel de módulo en `islr_conciliation.py`)

- `sanitize_rif(value) -> str`: mayúsculas, quita guiones/puntos/espacios (`'J-99.999.999-0' → 'J999999990'`). Cubre RF-3.
- `normalize_label(text) -> str`: minúsculas sin acentos ni doble espacio, para mapear etiquetas. Cubre RF-4/RF-5/RF-15.
- `to_amount(cell) -> (float, bool)`: devuelve `(0.0, True)` si la celda tiene texto no numérico; `(valor, False)` si es numérica o vacía. Cubre RF-16.
- `parse_conciliacion_xlsx(file_bytes) -> dict`: parser puro (openpyxl sobre `BytesIO`), sin `self.env`. Retorna:
  `{fiscal_year, rif, rubros: [{label, code, category, accounting, fiscal, not_deductible, legal_basis}], totals_xlsx: {...}, monto_a_pagar_xlsx, text_cells: [coords]}`. Cubre RF-1/RF-4/RF-5/RF-15/RF-16.
- `RUBRO_MAP`: dict `normalized_label → (code, category)` con los rubros canónicos del fixture (`ventas/income`, `inventario_inicial|compras|inventario_final/cost`, `sueldos_directivos|tributos_pagados|arrendamientos|otros_gastos|gastos_representacion|gastos_generales|gastos_transporte|gastos_trabajo|gastos_reparaciones|servicios_internet|gastos_depreciacion/deduction`). Etiqueta desconocida → `('otro', category_actual)`.

En el modelo: `_collect_warnings()` → `list[(code, message)]` y computes de totales; usan `self.env` solo vía campos (sin queries a BD).

## 3. Algoritmo (pseudocódigo)

### 3.1 Parseo (RF-1, RF-4, RF-5, RF-15, RF-16)
```
parse_conciliacion_xlsx(bytes):
    wb = openpyxl.load_workbook(BytesIO(bytes), data_only=True)   # except → ParseError("archivo corrupto")
    sheet = primera hoja con name.strip().casefold() == "conciliación fiscal"  # si no → ParseError("falta hoja")
    year = regex r'\d{4}' sobre la celda que contiene "Período Fiscal" (B6), usar el año de "al DD/MM/YYYY"
    rif  = primera celda de filas 1-12 que matchee r'^[VEJPG]-?\d{8,9}-?\d?$'
    rubros = []; seccion = None; totals_xlsx = {}; text_cells = []
    para fila en 13..46:                       # row 12 es cabecera
        label = B(fila) normalizado (strip)
        si label vacío → continuar
        si label ∈ {'INGRESOS','COSTOS DE VENTA','DEDUCCIONES'} → seccion = label; continuar
        si label empieza con 'TOTAL' o ∈ {'MERCANCIA DISPONIBLE','RENTA BRUTA','UTILIDAD NETA DEL EJERCICIO'}:
            totals_xlsx[clave(label)] = (to_amount(C), to_amount(D))   # referencia, no línea (RF-8)
            continuar
        si label contiene 'MONTO A PAGAR' → monto_a_pagar_xlsx = to_amount(F(fila)); continuar
        code, category = RUBRO_MAP.get(normalize_label(label), ('otro', seccion_actual))
        accounting,f1 = to_amount(C); fiscal,f2 = to_amount(D); noded,f3 = to_amount(E)
        si f1|f2|f3 → text_cells += coords
        rubros.append({label, code, category, accounting, fiscal, not_deductible: noded, legal_basis: F(fila)})
    agrupar rubros por (code, label normalizado): sumar las 3 columnas; si len(grupo) > 1 → flag 'duplicado'
    return {...}
```
`ParseError` → `UserError` en el wizard con el mensaje correspondiente.

### 3.2 Carga en wizard (RF-1, RF-2, RF-3)
```
_load_islr_conciliation_file():
    si no file → UserError
    data = parse_conciliacion_xlsx(self.file)
    candidatos = compliance.client donde sanitize_rif(rif) == sanitize_rif(data.rif)   (cubre RF-3)
    si vacío → UserError("RIF ... no existe; cree el cliente primero")
    si candidatos en >1 compañía:
        restringir por self.company_id (wizard, default compañía actual)
        si no queda exactamente 1 → UserError("seleccione la compañía")
    existing = reconciliation.search([client, year, company])
    guardar en el wizard: cliente, year, existing_id, rubros (dict en campo Json), totals, monto, text_cells
    state = 'preview'
```
```
_import_islr_conciliation():
    si existing_id y no replace_confirmed → UserError("confirme el reemplazo")   (RF-2)
    si existing y RIF guardado ≠ RIF archivo → el check de confirmación muestra advertencia extra (RF-2)
    con existing: line_ids.unlink(); si no: create con (client, company, fiscal_year)
    crear líneas (una por rubro, sequence por categoría)
    escribir totals_xlsx/monto_a_pagar_xlsx y recalcular; state='draft'
```

### 3.3 Compute y advertencias (RF-7 a RF-11, RF-17)
```
totales (depends line_ids):
    ingresos_col   = sum(l.amount para l.category=income y col)
    inv_ini, compras, inv_fin, deducciones = sum por code/category   (por columna)
    mercancia_disponible[col] = inv_ini + compras
    costo_venta[col]  = mercancia_disponible - inv_fin
    renta_bruta[col]  = ingresos - costo_venta
    utilidad_neta[col]= renta_bruta - deducciones
monto_a_pagar_calculado = 0.34 * utilidad_neta_fiscal        (RF-11)
_collect_warnings():
    por cada total recalculado vs totals_xlsx → ('descuadre', ...)          (RF-8)
    por línea: |accounting - (fiscal + not_deductible)| > 0.01 → ('identidad') (RF-9)
    ingresos_fiscales > 0 y sueldos_fiscal > 10% → ('tope')                 (RF-10)
    ingresos_fiscales == 0 → ('tope_sin_base')                              (RF-10)
    monto calculado vs monto_a_pagar_xlsx → ('monto')                       (RF-11)
    code 'otro' → ('rubro_desconocido')                                     (RF-5)
    grupos duplicados → ('duplicado')                                       (RF-15)
    text_cells → ('texto_numerico')                                         (RF-16)
warning_html = Html render de la lista (computed stored, depends de líneas y campos xlsx) (RF-17)
```

### 3.4 Ciclo de vida (RF-12, RF-14)
```
action_validate():  write({'state':'validated'}) con context skip_revert
                    pdf = report._render_qweb_pdf(action, self.id); guardar ir.attachment;
                    self.pdf_attachment_id = attachment
reconciliation.write(vals) / line.write(vals):   (excepto context skip_revert)
    si state == 'validated' y vals modifica líneas o datos → state='draft'; unlink pdf_attachment; pdf_attachment_id=False
```
Concurrencia: sin locks propios; el lock transaccional estándar de Odoo/PostgreSQL cubre el caso (NFR).

## 4. Interfaz

- Menú: "Cumplimiento VE" → "Conciliación ISLR" (sequence 42, entre Alertas y Factura Física).
- Lista: cliente, año fiscal, estado (badge), utilidad neta fiscal, monto calculado, monto Excel, icono de advertencias; filtros por año/estado; agrupar por cliente.
- Formulario: header con estado + [Validar] + [Imprimir PDF]; si `warning_html` → bloque `alert alert-warning`; pestaña Rubros: lista editable inline (categoría, etiqueta, contabilidad, fiscal, no deducible, precepto, modified_by/at readonly); pestaña Totales: pares contabilidad/fiscal read-only + monto calculado vs informado; pestaña Referencia: totales Excel detectados y notas.
- Wizard "Importar desde Excel": selector con el nuevo tipo; al cargar muestra cliente/año detectados, nº de rubros y advertencias de parseo; si ya existe el registro → checkbox "Confirmar reemplazo" visible y obligatorio.
- PDF: réplica del bloque principal con encabezado (cliente, RIF, período, compañía), tabla de rubros con preceptos, totales, monto a pagar y advertencias.

## 5. Decisiones técnicas

1. **Reutilizar el wizard existente** (`l10n.ve.import.wizard`) en vez de un wizard nuevo. Alternativa descartada: wizard propio; duplicaría campos/patrones ya resueltos (preview, log, modos) y fragmentaría la UX "Importar desde Excel".
2. **Modelo con líneas One2many + `code` Selection canónico** en vez de guardar el JSON del parser. Alternativa descartada: campo Json; no permite edición por rubro, trazabilidad ni reporte por línea (constitución #2 y RF-6).
3. **Parser puro a nivel de módulo** (bytes → dict). Alternativa descartada: método del wizard con `self`; dificulta testear parseo sin wizard y mezcla IO con UI.
4. **Recalcular + conservar referencia Excel + advertencia** (RF-8). Alternativa descartada: confiar en los totales del Excel (el fixture real ya descuadra) o rechazar la importación (bloquearía al contador).
5. **Tarifa 34% plana personas jurídicas (Art. 52 LISLR)** para el monto calculado, comparado contra F45 con advertencia. Alternativas descartadas: tarifa progresiva por UT (requiere valor UT y tabla, fuera de alcance declarado) y dejar solo el valor del Excel (perdería el control de descuadre).
6. **Trazabilidad con el patrón `modified_by/modified_at` de `vat.book.line`** en vez de crear un mixin nuevo. Alternativa descartada: mixin `TraceabilityMixin`; solo dos modelos lo necesitan y generaría deuda de refactor no pedida.
7. **PDF como attachment generado al validar** (se elimina al revertir), no impresión on-demand. Alternativa descartada: reporte solo bajo demanda; no cumpliría "invalidar el PDF anterior" al editar (RF-12).
8. **`sanitize_rif()` como helper puro local** en vez de campo computed en `compliance.client`. Alternativa descartada: computed stored; requeriría migración de datos y no aporta al caso de uso (comparación puntual en importación).
9. **Fixture versionado con el patrón cartelera** (quitar de `.gitignore` + exclude de `check-added-large-files`). Alternativa descartada: fixture generado en memoria; imposible por ser un archivo real del contador con bloques laterales (el test debe validar que se ignoran).

## 6. Estrategia de tests

Archivo `tests/test_islr_conciliation.py` (patrón `test_import_vat_book.py` para helpers openpyxl):

- `TestParseConciliacionFixture` — fixture real: hoja detectada sin distinguir mayúsculas, año 2025, RIF `J-99999999-0` sanitizado, rubros esperados (ventas, inventario inicial/compras/inventario final, sueldos, tributos, arrendamientos, otros, representación, generales, transporte, ley de trabajo, reparaciones, internet, depreciación), importes C14/D14, F45=47863.69, bloques laterales (años 2023, "SIN ACTIVIDAD") ignorados. RF-1, RF-4.
- `TestCompute` — sobre el fixture: mercancía disponible 1982288.76, costo de venta 1383802.26, renta bruta 607476.54 (contabilidad); deducciones recalculadas (412642.31) ≠ Excel (184979.44) → warning `descuadre`; utilidad neta recalculada; monto calculado 34% vs 47863.69 → warning `monto`. RF-7, RF-8, RF-11.
- `TestWarnings` — sintéticos: identidad rota (RF-9), tope excedido y base cero (RF-10), rubro desconocido (RF-5), duplicado suma + warning (RF-15), texto→0 + warning (RF-16), advertencias persistidas y recalculadas al editar (RF-17).
- `TestLifecycle` — reimportar mismo cliente/año exige confirmación y reemplaza sin duplicar (RF-2); validar genera attachment PDF (RF-12); editar una línea validada → vuelve a `draft` y elimina el attachment (RF-12/14); trazabilidad `modified_by/at` al editar (RF-6); lista/formulario accesibles y filtrables (RF-13).
- `TestStrictErrors` — hoja ausente/corrupta → UserError (RF-1); RIF inexistente → UserError (RF-3); RIF en dos compañías → UserError pidiendo compañía (RF-3).
- Comando: `docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager` → `0 failed ... of N tests` con N = 258 + nuevos; CI 3/3 verde.

## 7. Cobertura RF → componente

| RF | Componente |
|---|---|
| RF-1 | `parse_conciliacion_xlsx` (hoja case-insensitive, error) + wizard `_load_islr_conciliation_file` |
| RF-2 | wizard `_import_islr_conciliation` (`replace_confirmed`, aviso RIF) |
| RF-3 | `sanitize_rif` + búsqueda de cliente + desambiguación por compañía en el wizard |
| RF-4 | `RUBRO_MAP` + parser filas 12-46 cols B-F (totales excluidos) |
| RF-5 | parser (`otro`) + `_collect_warnings` |
| RF-6 | `modified_by/at` en líneas y cabecera |
| RF-7 | computes de totales (contabilidad y fiscal) |
| RF-8 | `totals_xlsx` + warning `descuadre` |
| RF-9 | warning `identidad` por línea |
| RF-10 | warning `tope` / `tope_sin_base` |
| RF-11 | `monto_a_pagar_calculado` + warning `monto` + campo editable informado |
| RF-12 | `action_validate` (attachment) + write-revert (unlink) + reporte QWeb |
| RF-13 | vistas lista/form + acción + menú |
| RF-14 | write-revert a `draft` sin bloquear |
| RF-15 | agrupación por etiqueta normalizada en parser + warning |
| RF-16 | `to_amount` + `text_cells` + warning |
| RF-17 | `warning_html` computed-stored |

Sin preguntas abiertas pendientes; la tarifa del 34% queda como decisión 5 y cualquier desviación real se surface vía la advertencia `monto`.
