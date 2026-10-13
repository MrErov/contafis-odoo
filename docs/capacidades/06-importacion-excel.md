# 06 - Importación desde Excel

## Propósito
Permitir a contadores importar datos masivos desde archivos Excel (.xlsx) para poblar y actualizar los modelos del módulo `l10n_ve_compliance_manager` sin ingreso manual, aprovechando que el trabajo contable en Venezuela se realiza mayormente en hojas de cálculo.

## Alcance

### Incluye (MVP - Fases 1 a 3)
- **Wizard de 6 pasos**: Subir → Mapear → Preview → Validar → Importar → Resultado
- **Plantillas dinámicas**: Generación de .xlsx con headers según modelo destino
- **Mapeo híbrido**: Auto-detección por nombre de columna + ajuste manual en UI
- **Validación 3 niveles**: Sintaxis → Referencial → Negocio
- **Preview unificado**: Modelo `l10n.ve.import.line` (fusionado preview + resultado)
- **Upsert por claves de negocio**: Evita duplicados, actualiza existentes
- **Modo strict/lax**: Configurable en wizard
- **Límite preview**: 50 filas por defecto (configurable), warning si excede
- **Importadores core (MVP)**:
  - `l10n.ve.compliance.client` (clientes + partner por RIF)
  - `l10n.ve.obligation` (obligaciones con due_date automático)
  - `l10n.ve.document` (documentos con fechas y estado)
  - `l10n.retention` (retenciones vinculadas a facturas)
- **Auditoría persistente**: Log con adjunto + JSON de IDs para futuro "Deshacer"
- **Botón "Deshacer"**: Solo preparación en log (implementación en fase futura)

### No incluye (Fuera del MVP - Trabajo Futuro)
- Importación de asientos contables (`account.move`) — requiere cuadre debe/haber, líneas múltiples, impuestos, analytic, moneda
- Adjuntos/imágenes en Excel (comprobantes, PDFs) — subir por separado
- Streaming para archivos > 10k filas (read_only streaming openpyxl)
- Reversión "Deshacer" desde log (botón en log) — solo preparación en log
- Importación programada (cron) / sincronización bidireccional Excel ↔ Odoo
- Multi-idioma plantillas (solo español en MVP)

## Modelos

### `l10n.ve.import.wizard` (TransientModel)
Wizard principal con 6 pasos controlados por `state`:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `import_type` | Selection | `obligation`, `document`, `client`, `retention` |
| `file` | Binary | Archivo .xlsx subido |
| `filename` | Char | Nombre original |
| `template_file` | Binary | Plantilla generada |
| `mapping_ids` | One2many | `l10n.ve.import.mapping` |
| `line_ids` | One2many | `l10n.ve.import.line` (preview + resultado unificado) |
| `state` | Selection | `draft` → `mapping` → `preview` → `validating` → `done` |
| `preview_limit` | Integer | Default 50, warning si archivo tiene más filas |
| `company_id` | Many2one | Multi-compañía, valida acceso |
| `mode` | Selection | `strict` (fallo total) / `lax` (continuar, default) |

### `l10n.ve.import.mapping` (Model)
Mapeo dinámico columna Excel → campo Odoo:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `wizard_id` | Many2one | `l10n.ve.import.wizard` |
| `col_index` | Integer | Índice 0-based |
| `column_letter` | Char | "A", "B", "C" (openpyxl.utils.get_column_letter) |
| `col_name` | Char | Header en Excel |
| `field_name` | Char | Nombre campo en Odoo |
| `field_type` | Char | `char`, `date`, `float`, `many2one`, `selection`, `boolean`, `integer` |
| `required` | Boolean | Campo obligatorio en Odoo |
| `relation_model` | Char | Modelo relacionado si many2one |
| `default_value` | Text | Valor por defecto (Text para valores complejos) |

### `l10n.ve.import.line` (TransientModel) — **Unificado: Preview + Resultado**
Fila parseada con estado evolutivo:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `wizard_id` | Many2one | `l10n.ve.import.wizard` |
| `row_index` | Integer | Índice fila en Excel (1-based) |
| `data` | Json | Valores parseados `{field_name: value}` |
| `state` | Selection | `draft` → `validated` → `imported` \| `updated` \| `error` \| `skipped` |
| `record_id` | Reference | Polimórfico: registro creado/actualizado |
| `record_name` | Char | Nombre legible del registro |
| `model_name` | Char | Modelo destino (`l10n.ve.obligation`, etc.) |
| `error_msg` | Text | Errores de validación/import |

### `l10n.ve.import.log` (Model) — Auditoría Persistente

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `wizard_id` | Many2one | Wizard origen |
| `user_id` | Many2one | Usuario que importó |
| `date` | Datetime | Fecha importación |
| `import_type` | Char | `obligation`, `document`, etc. |
| `file_name` | Char | Nombre archivo |
| `total_rows` | Integer | Total filas procesadas |
| `success_count` | Integer | Creados + actualizados |
| `error_count` | Integer | Filas con error |
| `skipped_count` | Integer | Filas omitidas |
| `record_ids` | Text | **JSON**: `[{model, id, name}, ...]` para futuro "Deshacer" |
| `attachment_id` | Many2one | `ir.attachment` con archivo original + log Excel |

---

## Reglas de Negocio

### 1. Claves Únicas de Upsert (Corregidas)
| Modelo | Clave única (upsert) |
|--------|----------------------|
| `l10n.ve.obligation` | `client_id` + `obligation_type_id` + `period` |
| `l10n.ve.document` | `client_id` + `document_type_id` + `number` |
| `l10n.ve.compliance.client` | `rif` |
| `l10n.retention` | `invoice_id` + `partner_id` |

> Los campos `name` son secuenciales automáticos; no sirven como clave de negocio.

### 2. Validación 3 Niveles
| Nivel | Qué valida | Ejemplo |
|-------|------------|---------|
| **1. Sintaxis** | Tipo, formato, rango, obligatorios | Fecha válida, número con `_parse_number()`, RIF formato |
| **2. Referencial** | Existencia en BD | Cuenta contable existe, partner existe, obligation_type existe |
| **3. Negocio** | Reglas del dominio | Cuadre debe/haber, RIF módulo 11, duplicados por clave única, fechas lógicas |

### 3. Utilidad `_parse_number(value)`
Maneja formatos numéricos venezolanos:
- `'1.234,56'` → `1234.56` (miles=punto, decimal=coma)
- `'1,234.56'` → `1234.56` (miles=coma, decimal=punto)
- `'1234.56'` → `1234.56`
- `'1234,56'` → `1234.56`
- Detecta locale por presencia de separadores. Retorna `float` o `None`.

### 4. Validación RIF (Módulo 11)
Algoritmo oficial venezolano para validar RIF en importación de clientes/obligaciones.

### 5. Modo de Importación
- **Strict**: Primer error → rollback total, no importa nada
- **Lax (default)**: Continúa procesando, reporta errores por fila, importa válidas

### 5. Preview Limit
- Default: 50 filas en preview
- Warning visible si archivo tiene más filas
- Configurable en wizard

### 6. Auditoría y "Deshacer"
- Log persistente guarda `record_ids` como JSON `[{model, id, name}, ...]`
- Botón "Deshacer" **FUERA del MVP** — solo se guardan IDs en log para fase futura
- Adjunto `ir.attachment` con archivo original + log Excel de resultados

---

## Criterios de Aceptación (Tests)

| Test | Descripción |
|------|-------------|
| `test_import_obligations_template` | Descargar plantilla obligaciones → headers correctos |
| `test_import_50_obligations` | Importar 50 obligaciones desde plantilla → 50 creadas |
| `test_upsert_duplicate_obligation` | Duplicado por `client_id+type+period` → actualiza existente |
| `test_invalid_row_continues` | Fila inválida → error en línea, continúa siguientes (modo lax) |
| `test_strict_mode_rollback` | Modo strict → rollback total en primer error |
| `test_rif_validation_modulo11` | RIF inválido → error en validación |
| `test_log_created_with_attachment` | Log creado con adjunto y estadísticas |
| `test_record_ids_json_in_log` | `record_ids` guarda JSON con IDs para futuro "Deshacer" |

---

## Referencias

- `docs/specs/01-calendario-seniat.md` — Obligaciones y due_date
- `docs/specs/02-gestion-alertas.md` — Alertas generadas tras import
- `docs/specs/03-cartelera-fiscal.md` — Documentos y vigencias
- `docs/specs/04-retenciones.md` — Retenciones y facturas
- `docs/specs/05-dashboard-reportes.md` — Score actualizado tras import
- Odoo base_import module (referencia arquitectura)
- openpyxl / xlsxwriter docs
- Algoritmo RIF módulo 11 (SENIAT)

---

## Trabajo Futuro (Fuera de Alcance MVP)

1. **Asientos contables (`account.move`)** — Parseo líneas agrupadas por `ref`, cuadre debe/haber, impuestos, analytic, moneda, reconciliación
2. **Adjuntos/imágenes** — Subida separada + referencia en Excel
3. **Streaming >10k filas** — `openpyxl.load_workbook(read_only=True)` streaming
3. **Botón "Deshacer" en log** — Lee `record_ids` JSON y elimina/revierte
4. **Importación programada (cron)** — Carpeta vigilada / SFTP
5. **Sincronización bidireccional** — Exportar a Excel cambios en Odoo
6. **Multi-idioma plantillas** — Headers traducidos
