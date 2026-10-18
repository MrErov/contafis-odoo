# Tasks 004 - Tablas de ISLR (Estimadas/Anticipos y Retenciones) en el Calendario SENIAT 2026

Spec: `specs/004-tablas-islr/spec.md` · Plan: `specs/004-tablas-islr/plan.md`

Reglas: una tarea a la vez, en orden de dependencia. Commit al terminar cada tarea si los tests pasan (el conteo oficial es el de Odoo). Sin archivos temporales.

Comando oficial de tests (única fuente del conteo):
`docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`

- [x] **T1. Precarga de datos de referencia est_islr/ret_islr 2026 (`data/islr_calendar_2026.xml`, `noupdate="1"` + comentario "sujetas a verificación con la Gaceta Oficial") + manifest + tests de precarga.** RF-1, RF-2, RF-3
      Hecho cuando: est_islr tiene 30 líneas (jun, sep, dic × 10 dígitos, offset 0) y ret_islr 120 (12 meses × 10 dígitos, offset 1); día = dígito del RIF + 10 en todas; editar un día y recargar el XML no pisa el cambio; suite ≥193 sin regresiones.

- [ ] **T2. Tipos de obligación "Estimadas de ISLR" y "Retenciones de ISLR" (`data/islr_obligation_types.xml`, `noupdate="1"`) + campo `generation_months` en el tipo + vista.** RF-4, RF-7
      Hecho cuando: ambos tipos existen con `tax_type='islr'` y su `seniat_table_code`; "Estimadas" trae `generation_months="6,9,12"`; los tipos son asignables a un cliente vía `applicable_type_ids`; el campo es editable en la vista del tipo.

- [ ] **T3. Generación de Estimadas: helper `_parse_generation_months` + `_generate_for_client` respeta `generation_months` (jun, sep, dic) + tests de cron e idempotencia.** RF-5, RF-7
      Hecho cuando: un cliente (no-SPE) con el tipo de Estimadas genera exactamente 3 obligaciones en un ciclo anual de ventana (meses 6, 9 y 12) y 0 en el resto; re-ejecutar no duplica.

- [ ] **T4. Cálculo por tabla sin gate `is_spe`: `_resolve_due_date` y `_is_calendar_available` para est_islr/ret_islr + alerta `calendar_missing` + tests (no-SPE, SPE, tabla faltante, fila faltante, corrimiento a día hábil).** RF-8, RF-9, RF-10, RF-11, RF-12
      Hecho cuando: cliente no-SPE con ret_islr `03/2026` dígito 0 → 2026-04-10; SPE conserva su comportamiento; año 2099 sin tabla → sin vencimiento y alerta `calendar_missing` al generar; tabla sin fila mes/dígito → vencimiento vacío; sábado 13/06/2026 → lunes 15/06/2026.

- [ ] **T5. Retenciones mensuales con `month_offset=1` + integración con el flujo de alertas existente + tests.** RF-6, RF-13
      Hecho cuando: la ventana de generación crea una obligación de retenciones por mes; el vencimiento usa el mes siguiente (p. ej. `12/2026` dígito 9 → 2027-01-19); una obligación ISLR pendiente cerca del vencimiento genera su alerta `due_soon` con el flujo configurado.

- [ ] **T6. Verificación visual (UI) y demo manual: tablas ISLR editables, tipos visibles, cliente con ambos tipos genera por cron, wizard de copia incluye est_islr/ret_islr.** RF-14
      Hecho cuando: en el navegador las tablas muestran 30/120 filas y son editables; los tipos aparecen en la vista del tipo; el botón/cron genera las obligaciones del cliente demo; copiar 2026→2099 duplica también est_islr/ret_islr (test).

- [ ] **T7. Cierre: suite completa, docs (`docs/memory.md`, `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md`, `SPEC.md`) y reporte de métricas.** Todos los RF
      Hecho cuando: `0 failed, 0 error(s) of N` con N = 193 + tests nuevos (T1–T6); `git status` solo con los archivos esperados; documentación del carácter "referencia editable" registrada.
