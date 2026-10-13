# 10 - Importación de Libro de Compras/Ventas desde Excel

## Propósito
Permitir que el contador migre sus libros de compras y ventas desde
Excel a Odoo para que el sistema reemplace al Excel como herramienta
de trabajo. El Excel queda como respaldo histórico; el sistema es
la fuente de verdad a partir de la migración. Es el canal Excel-first
complementario al canal Odoo-first de spec 09.

## Alcance
**Incluye:**
- 3 nuevas ramas del wizard l10n.ve.import.wizard:
  * import_type = 'vat_book_purchase' (hoja COMPRAS)
  * import_type = 'vat_book_sale' (hoja VENTAS)
  * import_type = 'vat_book_both' (ambas hojas en un solo archivo)
- Detección dinámica de la fila de headers (patrón spec 07)
- Parser de columnas específicas del Excel real del contador
  venezolano (formato libro IVA SENIAT)
- period_month deducido del header "Mes AGOSTO 2026" o del nombre
  del archivo
- Soporte histórico multi-mes: el contador importa una vez por mes,
  todos los meses conviven en la misma tabla con period_month distinto
- Libro en Odoo queda VIVO (no congelado):
  * Líneas importadas editables en vista list
  * Se pueden eliminar líneas erróneas
  * Re-importar el mismo mes hace upsert (no duplica)
  * Log en l10n.ve.import.log con record_ids JSON
- 2 plantillas descargables (Compras y Ventas) con headers exactos
  que el parser espera
- 1 plantilla combinada (Compras y Ventas) con 2 hojas
- Asignación automática de operation_code:
  * COMPRAS + base 16% > 0 → operation_code = '33'
  * VENTAS + base 16% > 0 → operation_code = '42'
  * Base reducida 8% → '333' (compras) / '443' (ventas)
  * Base 0 + no sujeta/no gravada → '30' (compras) / '40' (ventas)

**No incluye:**
- Importación multi-archivo en una sola sesión (una sesión por mes)
- Importación de la hoja PLANILLA (se calcula con action_load_from_book)
- Importación de asientos contables account.move (fase futura)
- Detección automática del período desde el nombre del archivo

## Modelos involucrados
- l10n.ve.import.wizard: nuevos valores en import_type
- l10n.ve.import.line: preview unificado (reutilizado)
- l10n.ve.vat.book.line: campos destino (ver spec 09)
- l10n.ve.import.log: auditoría persistente (reutilizado)

## Reglas de negocio
1. Detección dinámica de la fila de headers: buscar la fila que
   contiene "R.I.F." o "Factura" en las primeras 15 filas
2. Mapeo de columnas por nombre de header (no por posición fija)
   porque el Excel varía entre versiones
3. _parse_number() reutilizado para montos VE (1.234,56)
4. _validate_rif() reutilizado para RIF (módulo 11)
5. Asignación de operation_code según la base cargada (ver Alcance)
6. Retención: dirección según hoja:
   - COMPRAS → retention_direction = 'to_vendor'
   - VENTAS → retention_direction = 'by_buyer'
7. Filas con RIF vacío o "ANULADO" se omiten con warning
8. Upsert por (partner_id, invoice_number, control_number, period_month)
9. Multi-mes: cada importación procesa 1 mes. El histórico se
   consulta en vista pivot agrupado por period_month

## Criterios de aceptación (tests)
- test_import_vat_book_purchase_template: descarga plantilla COMPRAS
- test_import_vat_book_sale_template: descarga plantilla VENTAS
- test_import_10_purchases: importa el Excel real del cliente
  (fixture en repo) → 10 líneas con bases/IVA correctos
- test_import_10_sales: ídem VENTAS
- test_import_vat_book_upsert: re-importar no duplica
- test_import_vat_book_operation_codes: verifica 33/42/333/443
- test_import_vat_book_multi_month: importar agosto + septiembre,
  verificar que coexisten sin colisión
- test_import_vat_book_both_loads_two_sheets: vat_book_both carga
  ambas hojas y marca _book_type en cada línea
- test_import_vat_book_both_imports_all: vat_book_both importa
  creando vat.book.line de ambos tipos (3 purchase + 2 sale en test)

## Referencias
- docs/specs/06-importacion-excel.md (infraestructura wizard)
- docs/specs/07-cartelera-excel.md (detección dinámica headers)
- docs/specs/09-libro-compras-ventas.md (modelos destino, canal Odoo-first)

## Notas de implementación
- Reutilizar 100% de la infraestructura de Fase 2A-2B: _parse_number,
  _validate_rif, _validate_reference, _validate_business,
  _upsert_record, savepoints
- El Excel real del cliente tiene 2 hojas (COMPRAS, VENTAS). Cada
  importación procesa 1 hoja, no las 2.
- Detección de hoja: buscar nombre que contenga "COMPRAS" o
  "VENTAS" (case-insensitive). Fallback: hoja 1 = compras,
  hoja 2 = ventas.
- **vat_book_both**: Procesa ambas hojas del Excel en una sola
  importación. Cada import.line lleva data['_book_type'] ('purchase'
  o 'sale') para que el import cree vat.book.line con el book_type
  correcto. Si el Excel solo tiene una hoja, se procesa esa sin error.
- **Multi-rate en preview**: El preview crea múltiples import.line
  por factura cuando la factura tiene más de una tasa IVA (multi-rate).
  Por ejemplo, una factura con base 16% + base_no_credit genera
  2 import.line. Esto es intencional: en el import, cada línea crea
  una vat.book.line separada según el operation_code.
- **Filtrado de filas basura**: Se omiten filas donde falte RIF
  (`partner_vat` vacío) O donde `invoice_number` sea vacío, '0',
  'NONE' o 'BASE IMPONIBLE' (headers repetidos en medio de datos).

## Tests de integración con Excel real

El archivo tests/fixtures/Libro_COMPRAS_VENTAS_Ficticio.xlsx
contiene 10 facturas de compra y 10 de venta (1 anulada) con
datos ficticios. Los siguientes tests validan el flujo
end-to-end:

- test_import_real_fixture_purchase_12_lines
- test_import_real_fixture_sale_9_lines
- test_import_real_fixture_both_creates_21_lines
- test_import_real_fixture_purchase_idempotent
- test_import_real_fixture_purchase_totals_matches_excel
  (verificado con mutation test: cambiar base_general del
  fixture hace fallar el test)
- test_import_real_fixture_sale_anulada_skipped

## Notas de implementación adicionales

- El modelo vat.book.line unifica base_import_16 y vat_import_16
  dentro de base_general y vat_general (decisión de Fase F).
  El helper _compute_expected_totals_from_fixture hace la misma
  combinación al leer el Excel.
- El parser no usa read_only=True en openpyxl porque el acceso
  por índice de fila devuelve filas vacías.
- El header 'IVA Importación 16%' del fixture (sin 'de') se
  mapea via alias en VAT_BOOK_HEADER_MAP.
