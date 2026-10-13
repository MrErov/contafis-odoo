# 08 - Evidencia de Cartelera Fiscal

## Propósito
Adjuntar evidencia fotográfica o PDF de documentos de cartelera fiscal a cada snapshot (`l10n.ve.cartelera.status`), con transición automática del estado del snapshot según la evidencia agregada.

## Alcance
**Incluye:**
- Modelo `l10n.ve.cartelera.evidence`: `image`, `image_128`, `filename`, `file_size_mb`, `uploaded_by`, `uploaded_at`, `state`, `notes`
- Wizard `l10n.ve.cartelera.evidence.wizard` para subida desde form de snapshot
- Compresión automática de imágenes a 1024x1024 vía `odoo.tools.image.image_process`
- Límite de tamaño configurable (default 5 MB) vía `ir.config_parameter` `l10n_ve_compliance.evidence_max_size_mb`
- Transición automática: `missing` → `pending` (al crear evidence) → `valid` (al aceptar) / `rejected` (al rechazar). `unlink()` recalcula el estado
- Botón "Subir Evidencia" en form de `cartelera.status`
- Smart button `evidence_count`

**No incluye:**
- Firma digital / validación de contenido
- OCR o extracción de texto
- Integración con escáner físico

## Modelos involucrados
- `l10n.ve.cartelera.evidence`: `image` (Binary), `image_128` (computed stored), `file_size_mb` (computed), `state` (pending/accepted/rejected), `uploaded_by`, `uploaded_at`, `notes`
- `l10n.ve.cartelera.evidence.wizard`: `cartelera_status_id`, `image`, `filename`, `file_size_mb`, `notes`, `action_upload()`
- `l10n.ve.cartelera.status`: `evidence_ids` (O2m), `evidence_count` (computed), `_recompute_status_from_evidence()`

## Reglas de negocio
1. Solo un estado por snapshot que refleje la evidencia agregada: `accepted` → `valid`, `pending` → `pending`, solo `rejected` → `rejected`, sin evidence → no tocar
2. Tamaño máximo configurable; comprimir antes de validar
3. Formatos soportados: jpg, jpeg, png, webp, pdf
4. Imágenes se comprimen a 1024x1024 preservando aspect ratio
5. PDFs no se comprimen, solo se valida tamaño
6. Sin filename o extensión desconocida: no comprimir, validar tamaño, rechazar si formato no soportado

## Criterios de aceptación (tests)
- `test_evidence_create_missing_to_pending`: crear evidence con state=pending cambia status de missing a pending
- `test_evidence_accepted_to_valid`: evidence accepted → status valid
- `test_evidence_reject_only_when_no_accepted`: si hay accepted, rejected no cambia a rejected; solo rejected → rejected
- `test_evidence_unlink_recomputes`: unlink de evidence recalcula status; sin evidence no se toca el estado
- `test_evidence_image_size_limit`: imagen > 5 MB lanza ValidationError
- `test_evidence_image_compression`: wizard comprime imagen y crea evidence con file_size_mb > 0
- `test_evidence_image_compression_is_valid`: imagen comprimida es decodificable y tiene dimensiones correctas
- `test_partner_image_related`: `partner_image_1920` es related sin columna propia
- `test_cartelera_html_render`: renderizado HTML de cartelera con escape XSS

## Referencias
- docs/specs/03-cartelera-fiscal.md (tipos de documento, vigencias)
- docs/specs/07-cartelera-excel.md (importación cartelera desde Excel)
- AGENTS.md (anti-patterns #7, #8, #9)

## Notas de implementación
- NO usar `t-out` en `<t t-name="card">` de kanban. Usar `<field name="cartelera_html"/>` directo
- NO usar `kanban_image()` en Odoo 19 (eliminado en Odoo 17). Usar URL directa `/web/image/<model>/<id>/<field>`
- NO usar `widget="image"` sobre campos related non-stored en kanban (causa OwlError). Usar `<img>` con URL construida
