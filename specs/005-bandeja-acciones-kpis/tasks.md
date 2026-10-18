# Tasks 005 - Bandeja de vencimientos accionable y análisis (KPIs)

Spec: `specs/005-bandeja-acciones-kpis/spec.md` · Plan: `specs/005-bandeja-acciones-kpis/plan.md`

Reglas: una tarea a la vez, en orden de dependencia. Commit al terminar cada tarea si los tests pasan (el conteo oficial es el de Odoo). Sin archivos temporales.

Comando oficial de tests (única fuente del conteo):
`docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`

- [x] **T1. Acciones de modelo `action_mark_paid` / `action_reopen` en `l10n.ve.obligation` + tests (`tests/test_obligation_actions.py`).** RF-2, RF-3
      Hecho cuando: marcar pagada (single y múltiple) setea `paid` + `payment_date` hoy; reabrir deja `pending`, o `overdue` si el vencimiento ya pasó, limpia fecha/referencia y conserva el comprobante; `cancelled` queda fuera; suite ≥222 sin regresiones.

- [x] **T2. Wizard "Registrar pago" (`l10n.ve.obligation.payment.wizard`) + botón en fila de la bandeja y header del formulario + ACL + tests.** RF-1, RF-8
      Hecho cuando: el wizard abre con fecha hoy por defecto, guarda referencia y comprobante, y confirma con `action_mark_paid`; el botón no aparece en `cancelled`; usuario de solo lectura recibe AccessError.

- [x] **T3. Alerta manual: valor `manual` en `alert_type`, método `action_create_manual_alert`, botón "Crear alerta" (form + bandeja), dedupe contra pendientes/enviadas + tests.** RF-4, RF-5, RF-6
      Hecho cuando: crear alerta usa el canal del tipo, destinatario contador y link `wa.me` en WhatsApp; con alerta `pending`/`sent` existente no duplica y avisa; tras `done` permite crear nueva; `alert_type='manual'` visible.

- [x] **T4. Acciones masivas (server actions ligadas a la bandeja) + vistas de análisis (graph/pivot de obligaciones y alertas) + menú "Análisis" + tests de carga de vistas.** RF-2, RF-7
      Hecho cuando: "Marcar pagadas (hoy)" y "Reabrir seleccionadas" operan sobre `active_ids` y reportan conteos; las 4 vistas (graph/pivot × 2 modelos) cargan sin error, el menú existe y las acciones son `graph,pivot,list`.

- [x] **T5. Verificación visual en navegador (capturas) + docs (`02-gestion-alertas.md`, `05-dashboard-reportes.md`, `SPEC.md`) + cierre de fase.** Todos los RF
      Hecho cuando: capturas de bandeja con botones, wizard de pago y menú "Análisis" con gráfico; docs actualizadas; `0 failed, 0 error(s) of N` con N = 222 + tests nuevos; `git status` solo con archivos esperados.
      Cerrada: `0 failed, 0 error(s) of 245 tests`; capturas `docs/guia-usuario/assets/screenshots/11-01..11-04`; graph legible (estado × mes) y pivote con las 5 agrupaciones + medidas Monto/Número.
