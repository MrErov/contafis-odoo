# Plan 005 - Bandeja de vencimientos accionable y análisis (KPIs)

Spec: `specs/005-bandeja-acciones-kpis/spec.md`

## Arquitectura

Todo se resuelve con patrones nativos de Odoo 19, sin modelos nuevos de negocio:

### 1. Acciones de modelo (`models/obligation.py`)

- `action_mark_paid(self)`: single/bulk; valida elegibilidad (`pending`/`overdue`),
  setea `state='paid'` y `payment_date=today` si viene vacío; devuelve notificación
  con el conteo aplicado.
- `action_reopen(self)`: `paid` → `pending`/`overdue` según `due_date` vs hoy;
  limpia `payment_date` y `payment_reference`; conserva `payment_attachment`.
- `action_create_manual_alert(self)`: delega en el flujo existente
  (`_create_alert` + `_send_alert`), con `alert_type='manual'`; deduplica contra
  alertas `pending`/`sent` de la misma obligación (RF-5).
- Helper compartido `_get_reopen_state(self)` reutiliza la regla de `_mark_overdue`.

### 2. Wizard "Registrar pago" (`models/obligation_payment_wizard.py` + vista)

- TransientModel `l10n.ve.obligation.payment.wizard` con `obligation_id`,
  `payment_date` (default hoy), `payment_reference`, `payment_attachment`.
- Botón "Registrar pago": en la fila de la bandeja (`type="object"`) y en el header
  del formulario; el wizard confirma y llama a `action_mark_paid`.

### 3. Acciones masivas (data + vistas)

- Dos `ir.actions.server` con `bind_model`/`bind_view` sobre la lista de la bandeja
  ("Marcar pagadas (hoy)", "Reabrir seleccionadas") que iteran `active_ids`.
- Alternativa descartada: botón en header de lista (no nativo en Odoo 19 para
  acciones por selección; el menú ⚙ de acciones ligadas es el patrón estándar).

### 4. Alertas

- Nuevo valor `manual` en `l10n.ve.alert.alert_type` (+ `ALERT_TYPE_LABELS`).
- Reutilización directa de `_create_alert`/`_send_alert`; sin cambios de lógica de
  canales ni destinatarios.

### 5. Análisis (KPIs)

- `views/obligation_analysis_views.xml`: graph (bar, group by `state`) + pivot para
  `l10n.ve.obligation`; graph + pivot para `l10n.ve.alert`.
- Dos acciones `graph,pivot,list` + menú "Análisis" (sequence 50) bajo el menú raíz.
- Sin vistas OWL ni assets nuevos.

### 6. Seguridad

- Sin modelos ACL nuevos salvo el wizard (mapear a los grupos existentes igual que
  las ACL de `l10n.ve.obligation`: lectura para `group_account_user`, escritura para
  `group_account_manager` + `l10n_ve_compliance_accountant`).
- Los botones se muestran según permisos de escritura; el backend valida igual
  (AccessError natural del ORM).

## Archivos afectados

- `models/obligation.py` (acciones), `models/alert.py` (valores `manual`).
- `models/__init__.py` + nuevo `models/obligation_payment_wizard.py`.
- `views/obligation_views.xml` (botones fila + form), nuevo
  `views/obligation_payment_wizard_views.xml`, nuevo `views/obligation_analysis_views.xml`.
- `data/obligation_bulk_actions.xml` (server actions), `security/ir.model.access.csv`
  (wizard), `__manifest__.py`.
- `tests/test_obligation_actions.py` (nuevo), `tests/test_analysis_views.py` (carga de
  vistas), extensiones puntuales en `tests/test_obligation.py`.

## Estrategia de tests

- T1: `action_mark_paid`/`action_reopen` (single, bulk, mixtos, cancelada, vencida).
- T2: wizard (default hoy, apply, adjunto, botón visible en lista/forma).
- T3: alerta manual (crea, deduplica, canal WhatsApp genera link, tipo `manual`).
- T4: server actions existen y están ligadas; las vistas graph/pivot/pivot cargan
  (`arch` contiene los tags) y el menú Análisis existe.

## Riesgos y mitigaciones

- **Botón en lista con permisos**: Odoo evalúa `type="object"` por registro; validar
  en tests con usuario de solo lectura (record rule) para asegurar el AccessError.
- **Dedupe de alertas**: criterio RF-5 puede ocultar reenvíos legítimos; se mitiga
  permitiendo crear nueva cuando la anterior está `done`.
- **Regresión de warnings de vistas**: correr `-u` y grep de `CRITICAL`/warnings como
  en fases previas.
