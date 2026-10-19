# 07 - Importación Cartelera Fiscal desde Excel

## Propósito
Permitir la importación mensual de la cartelera fiscal desde el Excel matricial del contador: cada fila es una empresa (RIF + nombre) y las 36 columnas de documentos obligatorios (C01-C36) indican presencia/falta. Genera/actualiza clientes y snapshots mensuales (`l10n.ve.cartelera.status`) por cliente con estado de cada documento (válido, expirado, pendiente, rechazado, faltante).

## Alcance

### Incluye
- **Rama `cartelera`** en `l10n.ve.import.wizard` (`import_type = 'cartelera'`) con `cartelera_year`, `cartelera_month` y `mode` (strict/lax)
- **Hoja por mes**: enero..diciembre (UserError si la hoja no existe en el archivo)
- **Detección dinámica de estructura** (`_detect_cartelera_structure`):
  - Fila de headers: la que más coincide con `document_type.name`
  - Columna RIF: header `RIF`/`R.I.F.` o sniffing del patrón V/E/J/P/G sobre las filas de datos (los archivos reales de feb/dic traen una fila-ejemplo en A/B y los datos reales en C)
  - Columna nombre = RIF + 1
  - Bloque de documentos por posición: 36 columnas C01..C36 en orden de `document_type`; se amplía al mínimo esperado si el label "Total" cae sobre la última columna
  - Headers no reconocidos → campo `cartelera_unmatched_headers` (visible en la vista previa)
- **Validación 3 niveles** reutilizando infraestructura Fase 2:
  1. Sintaxis: hoja existe, estructura detectable, códigos mapeados
  2. Referencial: línea con RIF y nombre de empresa
  3. Negocio (`import.line._validate_business()`): RIF no vacío, año 2020-2100, mes 1-12, `statuses` con exactamente las 36 claves C01..C36
- **Importación por línea** (`_import_cartelera_line`):
  - Busca `l10n.ve.compliance.client` por RIF; `mode='strict'` → error si no existe; `mode='lax'` → crea `res.partner` (vat=RIF) + cliente
  - Genera snapshot vía `l10n.ve.cartelera.status.generate_snapshot(client_id, year, month, statuses)`
  - `statuses = {code: bool}` donde True = presente/válido, False = faltante
  - Upsert por constraint único `unique(client_id, year, month, document_type_id)`

### No incluye
- Carga de adjuntos/PDFs desde Excel (subida manual por documento)
- Validación de fechas de vencimiento contra vigencia legal (el formato matricial no trae fechas)
- Plantilla Excel propia (se importa el archivo real del contador)
- Importación de documentos de empleados/partners (`required_for != 'company'`)

## Modelos involucrados
- `l10n.ve.import.wizard`: campos `cartelera_year`, `cartelera_month`, `mode`, `cartelera_unmatched_headers`
- `l10n.ve.import.line`: preview/resultado unificado (estado `validated` → `imported` / `error`)
- `l10n.ve.cartelera.status`: snapshot mensual (36 registros por cliente/mes)
- `l10n.ve.document.type`: 36 tipos con `required_for='company'` y códigos C01-C36

## Reglas de negocio
1. **Formato Excel esperado**: matriz con una fila por empresa:
   - RIF (ej. `J-31234567-8`) y nombre en columnas adyacentes
   - 36 columnas de estatus en el orden de `l10n.ve.document.type` (C01..C36)
   - `Estado`: bool, "Sí"/"No", "1"/"0", "x" → bool (celda vacía → False)
2. **Mes/Año y hoja**: seleccionados en el wizard; la hoja (enero..diciembre) debe existir en el archivo
3. **Una importación = N empresas**: cada fila se convierte en un cliente (creado en modo lax si no existe)
4. **Estados resultado en snapshot**:
   - Estatus True → `state = 'valid'`
   - Estatus False → `state = 'missing'`
   - (Expirado/Rechazado/Pendiente requieren documento en BD, no vienen de Excel)
5. **Upsert**: Si ya existe snapshot para ese cliente/año/mes/tipo → actualiza estado
6. **Modo strict**: ninguna fila crea clientes nuevos; si un RIF no existe → error y rollback total

## Criterios de aceptación (tests)
| Test | Descripción |
|------|-------------|
| `test_parse_cartelera_sheet` | Parsear Excel sintético de enero → 2 líneas con 36 estatus cada una |
| `test_parse_nonjanuary_structure_sniffs_rif_column` | feb/dic sin header RIF y fila-ejemplo en A/B → el sniffing elige C y no genera líneas basura |
| `test_parse_real_cartelera_fixture_enero` | Fixture real (enero): 10 empresas × 36 estatus exactos |
| `test_parse_real_cartelera_fixture_febrero` | Fixture real (febrero): regresión del sniffing fuera de enero |
| `test_import_cartelera_creates_client` | Modo lax: RIF nuevo → crea res.partner + compliance.client |
| `test_import_cartelera_creates_snapshots` | Importar → 36 snapshots por cliente |
| `test_import_cartelera_upsert` | Re-importar mismo mes → actualiza estados, no duplica |
| `test_parse_cartelera_invalid_sheet` | Hoja inexistente → UserError |
| `test_validate_business_cartelera` | `_validate_business()`: claves C01..C36, año/mes válidos |
| `test_import_cartelera_strict_mode_no_client` | Modo strict con RIF nuevo → error sin crear cliente |
| `test_import_cartelera_via_action_import` | Flujo completo `action_import` |

## Referencias
- `docs/capacidades/03-cartelera-fiscal.md` — Tipos de documento, vigencias, alertas
- `docs/capacidades/06-importacion-excel.md` — Infraestructura wizard, validación 3 niveles, upsert
- `docs/capacidades/05-dashboard-reportes.md` — `document_score` se recalcula tras importación

## Notas de implementación
- Parser: `_detect_cartelera_structure()` + `_parse_cartelera_excel()` en `import_wizard.py`
- Carga: `_load_cartelera_file()` (parsea directo y va a preview, sin paso de mapeo)
- Importador: `_import_cartelera_line()` → crea cliente y llama a `CarteleraStatus.generate_snapshot()`
- Regresión con el fixture real versionado `tests/fixtures/Control_Cartelera_Fiscal_Prueba.xlsx` (2026-10-19: sniffing RIF feb/dic y bloque mínimo de 36 columnas cuando la fila de headers está desplazada)
