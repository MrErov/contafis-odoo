# 05 - Dashboard y Reportes

## Propósito
Proporcionar al contador una vista consolidada del estado de cumplimiento de todos sus clientes (multi-cliente) con semáforos visuales, puntuación numérica y reporte PDF exportable para entrega a gerencia/cliente.

## Alcance
**Incluye:**
- Modelo `l10n.ve.compliance.client`: `compliance_status` (`al_dia`/`pendiente`/`vencido`, computed), `compliance_score` (0-100, computed), `pending_alert_count` (computed)
- Vista kanban: tarjeta por cliente con semáforo (`compliance_status`), puntuación, badge "Alertas pendientes"
- Vista list/form: detalle obligaciones, alertas, documentos
- Reporte PDF `compliance_report.xml`: resumen ejecutivo por cliente (obligaciones vencidas, pendientes, alertas, documentos por vencer)

**No incluye:**
- BI/analytics avanzado (Power BI, Metabase)
- Exportación Excel (solo PDF nativo Odoo)
- Dashboard tiempo real (refresco manual o cron)

## Modelos involucrados
- `l10n.ve.compliance.client`: `compliance_status`, `compliance_score`, `pending_alert_count`, `obligation_ids`, `alert_ids`, `document_ids`, `last_alert_date`
- `l10n.ve.obligation`: `state`, `due_date` (fuente de score/status)
- `l10n.ve.alert`: `state` (fuente de pending_alert_count)
- `l10n.ve.document`: `state`, `expiry_date`
- `ir.actions.report`: `compliance_report` (qweb-pdf)

## Reglas de negocio
1. **compliance_status**:
   - `vencido`: existe obligación `overdue` O `pending` con `due_date < hoy` (excluye `cancelled`)
   - `pendiente`: existe obligación `pending` sin vencer (excluye `cancelled`)
   - `al_dia`: resto
2. **compliance_score**: `(total_activas - penalizadas) * 100 / total_activas`, redondeado 2 decimales.
   - `total_activas` = obligaciones ≠ `cancelled`
   - `penalizadas` = `overdue` O (`pending` Y `due_date` Y `due_date < hoy`)
   - Sin obligaciones activas → 100.0
3. **pending_alert_count**: alertas vinculadas al cliente con `state=pending`.
4. **Kanban**: usa `pending_alert_count` (campo computed), no `sum()` inline.
5. **Reporte PDF**: agrupa por cliente → obligaciones vencidas, pendientes, alertas pendientes, documentos por vencer (<30 días).

## Criterios de aceptación (tests)
- `test_compliance_score`: cliente con 1 pagada + 1 pendiente no vencida → 100.0; agrega vencida → 66.67; marca vencida como `cancelled` → 100.0; cliente sin obligaciones → 100.0; score siempre 0-100.

## Referencias
- docs/specs/01-calendario-seniat.md (due_date origen de score)
- docs/specs/02-gestion-alertas.md (alertas → pending_alert_count, last_alert_date)
- docs/specs/03-cartelera-fiscal.md (documentos → reporte)
