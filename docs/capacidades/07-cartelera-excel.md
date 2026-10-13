# 07 - Importación Cartelera Fiscal desde Excel

## Propósito
Permitir la importación mensual de la cartelera fiscal (36 documentos obligatorios C01-C36) desde Excel, generando snapshots mensuales (`l10n.ve.cartelera.status`) por cliente con estado de cada documento (válido, expirado, pendiente, rechazado, faltante).

## Alcance

### Incluye
- **Rama `cartelera`** en `l10n.ve.import.wizard` (`import_type = 'cartelera'`)
- **Parser** que lee columnas: `Código` (C01..C36), `Estado` (Sí/No o 1/0), `Vencimiento` (opcional)
- **Validación 3 niveles** reutilizando infraestructura Fase 2:
  1. Sintaxis: código existe en `l10n.ve.document.type`, estado parseable
  2. Referencial: cliente existe, tipos de documento cargados
  3. Negocio: 36 filas esperadas, duplicados por código, mes/año coherentes
- **Generación de snapshot** vía `l10n.ve.cartelera.status.generate_snapshot(client_id, year, month, statuses)`
  - `statuses = {code: bool}` donde True = presente/válido, False = faltante
  - Upsert por constraint único `unique(client_id, year, month, document_type_id)`
- **Plantilla dinámica** con 36 filas pre-rellenadas (códigos C01-C36)

### No incluye
- Carga de adjuntos/PDFs desde Excel (subida manual por documento)
- Validación de fechas de vencimiento contra vigencia legal (solo parseo básico)
- Importación de documentos de empleados/partners (`required_for != 'company'`)

## Modelos involucrados
- `l10n.ve.import.wizard`: `import_type = 'cartelera'`, campos `year`, `month`, `client_id`
- `l10n.ve.import.line`: preview/resultado unificado (estado `validated` → `imported`)
- `l10n.ve.cartelera.status`: snapshot mensual (36 registros por cliente/mes)
- `l10n.ve.document.type`: 36 tipos con `required_for='company'` y códigos C01-C36

## Reglas de negocio
1. **Formato Excel esperado**: columnas `Código`, `Estado`, `Vencimiento`
   - `Estado`: "Sí"/"No", "1"/"0", "true"/"false" → bool
   - `Vencimiento`: fecha opcional (DD/MM/YYYY), si vacía → `expiry_date = False`
2. **Mes/Año**: Seleccionados en wizard (no en Excel), aplican a todas las filas
3. **Cliente**: Seleccionado en wizard (no en Excel), una importación = un cliente
4. **Estados resultado en snapshot**:
   - `Estado = True` → `state = 'valid'`
   - `Estado = False` → `state = 'missing'`
   - (Expirado/Rechazado/Pendiente requieren documento en BD, no vienen de Excel)
5. **Upsert**: Si ya existe snapshot para ese cliente/año/mes/tipo → actualiza estado

## Criterios de aceptación (tests)
| Test | Descripción |
|------|-------------|
| `test_import_cartelera_template` | Descargar plantilla cartelera → 36 filas con códigos C01-C36 |
| `test_import_36_cartelera` | Importar 36 filas (algunas Sí, otras No) → 36 snapshots creados |
| `test_snapshot_from_excel` | Verificar `state='valid'` para Sí, `state='missing'` para No |
| `test_upsert_cartelera_snapshot` | Re-importar mismo mes → actualiza estados, no duplica |

## Referencias
- `docs/specs/03-cartelera-fiscal.md` — Tipos de documento, vigencias, alertas
- `docs/specs/06-importacion-excel.md` — Infraestructura wizard, validación 3 niveles, upsert
- `docs/specs/05-dashboard-reportes.md` — `document_score` se recalcula tras importación

## Notas de implementación (Fase C)
- Parser en `import_wizard.py` → `_parse_cartelera_row()`
- Importador en `import_wizard.py` → `_import_cartelera()`
- Llama a `CarteleraStatus.generate_snapshot(client_id, year, month, statuses)`
- `statuses` dict construido desde líneas validadas: `{line.data['Código']: line.data['Estado_bool']}`
