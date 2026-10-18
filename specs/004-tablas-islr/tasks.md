# Tasks 004 - Tablas de ISLR (Estimadas/Anticipos y Retenciones) en el Calendario SENIAT 2026

Spec: `specs/004-tablas-islr/spec.md` · Plan: `specs/004-tablas-islr/plan.md`

Reglas: una tarea a la vez, en orden de dependencia. Commit al terminar cada tarea si los tests pasan (el conteo oficial es el de Odoo). Sin archivos temporales.

Comando oficial de tests (única fuente del conteo):
`docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`

- [x] **T1. Precarga de datos de referencia est_islr/ret_islr 2026 (`data/islr_calendar_2026.xml`, `noupdate="1"` + comentario "sujetas a verificación con la Gaceta Oficial") + manifest + tests de precarga.** RF-1, RF-2, RF-3
      Hecho cuando: est_islr tiene 30 líneas (jun, sep, dic × 10 dígitos, offset 0) y ret_islr 120 (12 meses × 10 dígitos, offset 1); día = dígito del RIF + 10 en todas; editar un día y recargar el XML no pisa el cambio; suite ≥193 sin regresiones.

- [x] **T2. Tipos de obligación "Estimadas de ISLR" y "Retenciones de ISLR" (`data/islr_obligation_types.xml`, `noupdate="1"`) + campo `generation_months` en el tipo + vista.** RF-4, RF-7
      Hecho cuando: ambos tipos existen con `tax_type='islr'` y su `seniat_table_code`; "Estimadas" trae `generation_months="6,9,12"`; los tipos son asignables a un cliente vía `applicable_type_ids`; el campo es editable en la vista del tipo.
      Nota (2026-10-18): el prompt de la tarea pedía además `_generate_for_client` respetando `generation_months` (helper `_parse_generation_months`) y sus tests de mayo/junio y retenciones mensuales; se implementaron aquí. El resto de T3 (ciclo anual de ventana e idempotencia del cron) queda pendiente.

- [x] **T3. Generación de Estimadas: helper `_parse_generation_months` + `_generate_for_client` respeta `generation_months` (jun, sep, dic) + tests de cron e idempotencia.** RF-5, RF-7
      Hecho cuando: un cliente (no-SPE) con el tipo de Estimadas genera exactamente 3 obligaciones en un ciclo anual de ventana (meses 6, 9 y 12) y 0 en el resto; re-ejecutar no duplica.
      Nota (2026-10-18): cerrada al verificar el alcance pendiente (ciclo anual de ventana + idempotencia). `test_generate_estimadas_only_configured_months` se amplió a los 12 meses (6/9/12 → 1, resto → 0; re-ejecutar el mes 6 → 0; total 3) y `test_generate_retenciones_monthly` cubre el mensual. Sin cambios en la lógica de generación.

- [x] **T4. Cálculo por tabla sin gate `is_spe`: `_resolve_due_date` y `_is_calendar_available` para est_islr/ret_islr + alerta `calendar_missing` + tests (no-SPE, SPE, tabla faltante, fila faltante, corrimiento a día hábil).** RF-8, RF-9, RF-10, RF-11, RF-12
      Hecho cuando: cliente no-SPE con ret_islr `03/2026` dígito 0 → 2026-04-10; SPE conserva su comportamiento; año 2099 sin tabla → sin vencimiento y alerta `calendar_missing` al generar; tabla sin fila mes/dígito → vencimiento vacío; sábado 13/06/2026 → lunes 15/06/2026.
      Nota (2026-10-18): 7 tests nuevos en `TestIslrDueDateWithoutSpe` (rojo→verde). `_resolve_due_date`: est_islr/ret_islr pasan por calendario sin gate `is_spe`; `_is_calendar_available`: exige la tabla del año para est_islr/ret_islr (a1/a2 conservan la regla solo-SPE). Suite: 0 failed, 0 error(s) of 212 tests.

- [x] **T5. Retenciones mensuales con `month_offset=1` + integración con el flujo de alertas existente + tests.** RF-6, RF-13
      Hecho cuando: la ventana de generación crea una obligación de retenciones por mes; el vencimiento usa el mes siguiente (p. ej. `12/2026` dígito 9 → 2027-01-19); una obligación ISLR pendiente cerca del vencimiento genera su alerta `due_soon` con el flujo configurado.
      Nota (2026-10-18): sin tocar la lógica (ya probada en T2/T3/T4), se agregaron los tests de cierre: `test_retenciones_december_rolls_into_next_year` (12/2026 dígito 9 → 2027-01-19), `test_islr_obligation_reuses_alert_flow` (due_soon por el flujo del tipo: destinatario contador, canal email) y la cobertura de ventana mensual en `TestDemoDataIslr` (1 retención por mes de la ventana, idempotente). Suite: 0 failed, 0 error(s) of 217 tests.

- [x] **T6. Verificación visual (UI) y demo manual: tablas ISLR editables, tipos visibles, cliente con ambos tipos genera por cron, wizard de copia incluye est_islr/ret_islr.** RF-14
      Hecho cuando: en el navegador las tablas muestran 30/120 filas y son editables; los tipos aparecen en la vista del tipo; el botón/cron genera las obligaciones del cliente demo; copiar 2026→2099 duplica también est_islr/ret_islr (test).
      Nota (2026-10-18): `demo/demo_data.xml` asigna "Estimadas de ISLR" y "Retenciones de ISLR" al cliente demo no-SPE (Servicios Andinos, J-29876543-1); el `<function>` del demo genera 8 obligaciones, incluidas Retenciones 10/2026 → 2026-11-11 y 11/2026 → 2026-12-11. Verificado con Chrome DevTools en BD desechable (`contea_004_demo`, `module force-demo`, eliminada al cerrar): bandeja "Próximos vencimientos" muestra "Retenciones de ISLR" (captura `spec004-t5-t6-proximos-vencimientos.png`), Calendario SENIAT con est_islr 30 filas (6/0/10 …) y ret_islr 120 filas editables, tipos asignados visibles en el cliente. Copia 2026→2027 de las 4 tablas cubierta por `TestCopyCalendarWizard` (RF-14). Tests de demo rojo→verde (`TestDemoDataIslr`, 3 tests). Ayuda de `seniat_table_code` corregida en `models/obligation_type.py`.

- [ ] **T7. Cierre: suite completa, docs (`docs/memory.md`, `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md`, `SPEC.md`) y reporte de métricas.** Todos los RF
      Hecho cuando: `0 failed, 0 error(s) of N` con N = 193 + tests nuevos (T1–T6); `git status` solo con los archivos esperados; documentación del carácter "referencia editable" registrada.
