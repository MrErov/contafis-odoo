# 09 - Libro de Compras/Ventas y Planilla IVA 99030

## Propósito
Reemplazar los Excel de libro de compras/ventas y Planilla IVA 99030 que los contadores venezolanos llenan a mano cada mes. Generar los 48 ítems de la Forma 99030 automáticamente desde movimientos contables.

## Alcance
**Incluye:**
- ✅ Modelo `l10n.ve.vat.book.line` con `book_type` (purchase/sale), `period_month`, partner info, `invoice_number`, `control_number`, `operation_code`, `total_with_vat`, `base_general`, `vat_general`, `base_reduced`, `vat_reduced`, `base_no_credit`, `base_not_subject`, `base_not_taxed`, `retention_number`, `vat_retained`, `retention_direction` (by_buyer/to_vendor/to_third)
- ✅ Wizard `l10n.ve.vat.book.generate` desde `account.move`
- ✅ Modelo `l10n.ve.vat.return` con los 48 ítems de la Forma 99030
- ✅ Arrastre de excedente de crédito fiscal (item_60 mes N → item_20 mes N+1)
- ✅ Reporte PDF Forma 99030 imprimible

**No incluye:**
- Envío electrónico al SENIAT (el portal no acepta archivos)
- Conciliación ISLR (va en spec 11 separada)
- Importación desde Excel de libros existentes (spec 10, Fase G)

## Modelos involucrados

### `l10n.ve.vat.book.line`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `book_type` | Selection | `purchase` / `sale` |
| `period_month` | Char | Formato `YYYY-MM` |
| `partner_id` | Many2one | Proveedor o cliente |
| `invoice_number` | Char | Número de factura |
| `control_number` | Char | Número de control SENIAT |
| `operation_code` | Char | Código SENIAT (40/41/42/442/443/452/453/33/34/332/333/342/343) |
| `total_with_vat` | Float | Total con IVA |
| `base_general` | Float | Base imponible alícuota general |
| `vat_general` | Float | IVA alícuota general |
| `base_reduced` | Float | Base alícuota reducida |
| `vat_reduced` | Float | IVA alícuota reducida |
| `base_no_credit` | Float | Base sin crédito fiscal |
| `base_not_subject` | Float | Base no sujeta |
| `base_not_taxed` | Float | Base no gravada |
| `retention_number` | Char | Número de comprobante retención |
| `vat_retained` | Float | IVA retenido |
| `retention_direction` | Selection | `by_buyer` / `to_vendor` / `to_third` |

### `l10n.ve.vat.book.generate` (TransientModel)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `period_month` | Char | Mes a generar `YYYY-MM` |
| `company_id` | Many2one | Compañía |
| `action_generate()` | Method | Genera líneas desde `account.move` |

### `l10n.ve.vat.return`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `period_month` | Char | Mes `YYYY-MM` |
| `company_id` | Many2one | Compañía |
| `item_XX` (48 campos) | Float | Ítems fijos de la Forma 99030 |
| `action_load_from_book()` | Method | Carga ítems desde `vat.book.line` |
| `item_20` | Float | Computed desde item_60 mes anterior |

## Reglas de negocio
1. `period_month` formato `YYYY-MM` (Char), consistente con `cartelera.status`
2. Operación 42 (ventas gravadas 16%): base + IVA van a item_42
3. Operación 33/34 (compras gravadas 16%): base + IVA van a item_33/34
4. Excedente: item_60 = max(0, item_39 - item_49). Si positivo, arrastra al item_20 del mes siguiente. Si negativo, se paga (item_53)
5. Retenciones del período (item_66) se descuentan del total a pagar
6. Los 48 ítems son campos fijos, no líneas dinámicas (la planilla es rígida por diseño SENIAT)
7. Los códigos de operación SENIAT en el libro son: 40 (ventas no gravadas), 41 (exportación), 42 (ventas gravadas 16%), 442 (ventas + alícuota adicional), 443 (ventas alícuota reducida), 33 (compras gravadas 16%), 34 (IVA compras), 332/342 (compras + adicional), 333 (base reducida 8% compras), 343 (IVA reducido 8% compras)

### Rangos de los 48 ítems de la Forma 99030
| Rango | Ítems |
|-------|-------|
| Débitos | 40, 41, 42, 43, 442, 443, 452, 453, 46, 47, 48, 80, 49 |
| Créditos | 30, 31, 32, 312, 313, 322, 323, 33, 34, 332, 333, 342, 343, 35, 36, 70, 37, 71, 20, 21, 81, 38, 82, 39 |
| Autoliquidación | 53, 60, 22, 51, 24, 78, 54, 66, 72, 73, 74, 55, 67, 56, 57, 68, 75, 76, 77, 58, 69, 90 |

## Criterios de aceptación (tests)
- `test_book_generate_from_moves`: genera líneas desde `account.move` del período
- `test_book_no_duplicates`: no genera líneas duplicadas por factura
- `test_vat_return_load_from_book`: carga ítems desde `vat.book.line`
- `test_vat_return_excedente_arrastre`: item_60 positivo arrastra a item_20 del mes siguiente
- `test_vat_return_pdf_renders_48_items`: reporte PDF contiene los 48 ítems

## Referencias
- docs/specs/04-retenciones.md (retenciones vinculadas a facturas)
- Forma 99030 SENIAT
- Providencia SNAT/2025/82 (formularios vigentes)

## Trabajo Futuro
- Conciliación ISLR (spec 11)
- Envío electrónico si SENIAT habilita API
- Importación de libros históricos desde Excel (spec 10)

## Notas de implementación
- **retention_direction** (by_buyer/to_vendor/to_third) en lugar de `vat_retained_by_buyer` para distinguir retenciones de ventas vs compras
- **item_70 = item_36** (créditos fiscales deducibles = IVA compras)
- **item_71 = item_70 + item_37** (prorrata)
- **item_39 = item_71 + item_20 - item_21 - item_81 + item_38 - item_82**
- **Multi-rate por factura**: se crea una línea de vat.book.line por cada tasa IVA distinta en la misma factura
- **Sin detección automática de exportación** (l10n_latam_invoice_document no está instalado). TODO Fase G.
- **item_43 es obligatorio** (IVA ventas 16%) además de item_42 (base)
- **action_load_from_book()** es no-op si no hay líneas del período (no lanza UserError)

## Importación desde Excel (canal alterno)

Además del canal Odoo-first (account.move → wizard → libro), el
sistema permite importar el libro directamente desde el Excel que
usa el contador. Ver spec 10.

## Export a Excel

### Export de vat.book.line

- Wizard: `l10n.ve.vat.book.export.wizard`
- Campos: `period_month`, `company_id`, `book_type` (purchase/sale/both)
- Genera XLSX con headers idénticos al template de import (round-trip)
- 1 hoja por book_type (COMPRAS / VENTAS / both con 2 hojas)
- Fila TOTAL GENERAL con sumas por columna (no combina base con IVA)
- Retenciones separadas por `retention_direction`
- Acción expuesta vía Actions menu (`binding_model_id`)

### Export de vat.return (Planilla 99030)

- Método `action_export_99030_xlsx()` en `vat.return`
- Campos nuevos: `export_file` (Binary), `export_filename` (Char)
- Genera XLSX con 3 secciones: DÉBITOS, CRÉDITOS, AUTOLIQUIDACIÓN
- Los 59 campos `item_XX` del modelo con conceptos SENIAT literales (extraídos del Excel real del contador, NO del PDF original)
  - 48 corresponden a los ítems numerados de la planilla SENIAT oficial
  - 11 son campos auxiliares (subtotales y ajustes) que el formulario calcula pero no numera físicamente
- Botón "Exportar a Excel" en el header del form

### Corrección del PDF

El PDF original tenía conceptos inventados. Se corrigieron los 59
conceptos con los nombres literales del SENIAT (mismo origen que el
XLSX). El layout del PDF no cambió.

### Nota de implementación

Si la compañía no tiene RIF seteado, el export muestra None en la
columna RIF. Pendiente: agregar fallback `company.vat or ''` en el
método de export XLSX.
