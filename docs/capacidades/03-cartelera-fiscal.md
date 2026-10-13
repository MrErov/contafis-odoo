# 03 - Cartelera Fiscal (Documentos)

## Propósito
Gestionar la vigencia y renovación de documentos legales/fiscales de empresas y terceros (RIF, patente municipal, certificado IVSS, etc.) con alertas automáticas de expiración y faltantes.

## Alcance
**Incluye:**
- Modelo `l10n.ve.document.type`: tipo de documento, institución emisora, días de vigencia, días de alerta previa, quién lo requiere (company/partner/employee)
- Modelo `l10n.ve.document`: instancia por cliente, número, fechas emisión/vencimiento, adjunto, estado (`valid`/`expired`/`pending`/`rejected`)
- Alertas automáticas: `document_expiring` (antes de vencer) y `document_missing` (requerido pero no cargado)
- Renovación: al subir nuevo adjunto con fechas actualizadas, estado vuelve a `valid`

**No incluye:**
- Validación de contenido del adjunto (manual por contador)
- Firma digital / autenticación externa

## Modelos involucrados
- `l10n.ve.document.type`: `validity_days`, `renewal_alert_days`, `required_for`, `alert_channel`, `institution_id`
- `l10n.ve.document`: `client_id`, `document_type_id`, `number`, `issue_date`, `expiry_date`, `attachment`, `state`, `last_alert_date`
- `l10n.ve.compliance.client`: `document_ids` (O2m)
- `l10n.ve.alert`: tipos `document_expiring`, `document_missing`

## Reglas de negocio
1. **Vigencia**: `expiry_date = issue_date + validity_days` (configurable por tipo).
2. **Estado automático**:
   - `valid`: hoy ≤ `expiry_date`
   - `expired`: hoy > `expiry_date`
   - `pending`: recién creado, sin validar
   - `rejected`: contador marca inválido
3. **Alerta expiración**: `renewal_alert_days` antes de `expiry_date` si `state=valid`.
4. **Alerta faltante**: Cron detecta `required_for` sin documento vinculado → `document_missing`.
5. **Canal**: Según `alert_channel` del tipo (`email`, `whatsapp`, `both`).

## Criterios de aceptación (tests)
- `test_document_expiry`: crea documento con `expiry_date` pasado → estado `expired`; con `expiry_date` futuro → `valid`; verifica alerta `document_expiring` se genera en ventana.

## Referencias
- docs/specs/02-gestion-alertas.md (motor de alertas compartido)
- Gaceta Oficial (vigencias según tipo de documento)
