# 02 - Gestión de Alertas

## Propósito
Generar y enviar notificaciones automáticas a contadores y clientes sobre vencimientos fiscales, pagos faltantes y documentos por vencer. Multi-canal: email (plantillas Odoo) y WhatsApp (wa.me, sin API Meta).

## Alcance
**Incluye:**
- Modelo `l10n.ve.alert` con tipos: `due_soon`, `overdue`, `missing_payment`, `document_expiring`, `document_missing`
- Cron diario `_cron_generate_compliance_alerts` que escanea obligaciones y documentos
- Canales: `email` (mail.template + mail.mail) y `whatsapp` (enlace wa.me con mensaje prellenado)
- `mail.activity` para seguimiento interno en chatter
- Estados de alerta: `pending` → `sent` → `done`

**No incluye:**
- WhatsApp Business API (costo/dependencia Meta)
- Alertas push/SMS

## Modelos involucrados
- `l10n.ve.alert`: `alert_type`, `date`, `state`, `channel`, `message`, `recipient_ids`
- `l10n.ve.obligation`: `due_date`, `state`, `alert_ids` (O2m)
- `l10n.ve.document`: `expiry_date`, `state`, `alert_ids` (O2m)
- `l10n.ve.compliance.client`: `alert_ids`, `last_alert_date`
- `l10n.ve.obligation.type`: `alert_days_before`, `alert_channel`, `alert_enabled`, `alert_on_overdue`, `alert_on_missing_payment`

## Reglas de negocio
1. **due_soon**: X días antes (`alert_days_before`) del `due_date` si `state=pending`.
2. **overdue**: Al día siguiente del `due_date` si `state=pending` (cron marca `overdue`).
3. **missing_payment**: Si `state=overdue` y pasa `missing_payment` días sin pago.
4. **document_expiring**: X días antes (`renewal_alert_days`) del `expiry_date` si `state=valid`.
5. **document_missing**: Si `required_for` aplica y no existe documento vinculado al cliente.
6. **Canal**: Según `alert_channel` del tipo obligación/documento (`email`, `whatsapp`, `both`).
7. **Deduplicación**: No crear alerta duplicada misma `alert_type` + `obligation_id`/`document_id` en `pending`.

## Criterios de aceptación (tests)
- `test_cron_generate_alerts`: verifica creación de alertas `due_soon` (3 días antes), `overdue` (vencida), y que no duplica alertas existentes.

## Referencias
- docs/specs/01-calendario-seniat.md (due_date origen de due_soon/overdue)
- docs/specs/03-cartelera-fiscal.md (document_expiring/document_missing)
- docs/specs/05-dashboard-reportes.md (last_alert_date en cliente)
