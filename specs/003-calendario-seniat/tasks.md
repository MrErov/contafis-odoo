# Tasks 003 - Calendario SENIAT: vencimientos automáticos por último dígito del RIF

Spec: `specs/003-calendario-seniat/spec.md` · Plan: `specs/003-calendario-seniat/plan.md`

Reglas: una tarea a la vez, máximo 20-30 min cada una, en orden de dependencia.
Commit al terminar cada tarea si los tests pasan. Sin archivos temporales.

Comando oficial de tests (única fuente del conteo):
`docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`

- [x] **T1. Modelos `l10n.ve.seniat.calendar.table` + `l10n.ve.seniat.calendar`: campos, constraints (`models.Constraint`), ACL, `__init__` y manifest.** RF-1
      Hecho cuando: `-u l10n_ve_compliance_manager` termina sin error; en shell inline se crea una tabla+línea y el constraint rechaza duplicados (year, code) y (table, month, digit); los 121 tests actuales siguen en verde.

- [x] **T2. Precarga calendario 2026 (a.1 y a.2) en `data/seniat_calendar_2026.xml` con `noupdate="1"` + vistas y menú "Calendario SENIAT".** RF-1, RF-2, RF-3
      Hecho cuando: shell inline reporta 120 líneas a.1 + 120 a.2 para 2026 (spot: digit 0 enero a.1=28 / a.2=15); editar un `day` en la UI y correr `-u` no pisa el cambio.

- [x] **T3. Modelo `l10n.ve.bank.holiday` + precarga 2026 (fuente oficial verificada) + vistas y menú "Feriados bancarios".** RF-19
      Hecho cuando: los feriados 2026 cargan sin duplicados (constraint `UNIQUE(date)`), el menú aparece en Configuración y un año futuro se puede cargar/editar desde la UI.

- [x] **T4. Campos de configuración: `is_spe` y `applicable_type_ids` en cliente; `seniat_table_code`, `periodicity` quincenal y `alert_cc_client` en tipo; vistas y ayuda.** RF-5
      Hecho cuando: en UI un cliente se marca SPE y se le asignan tipos; un tipo IVA con quincenal + a1 guarda sin error; los 121 tests siguen en verde.

- [x] **T5. Cálculo de vencimientos: campo `quincena` (`monthly`/`q1`/`q2`), `_resolve_due_date_calendar`, regla no-SPE día 15, corrimiento `_shift_to_next_banking_day` y reimplementación de `'1-15'` vía tabla a.1.** RF-6, RF-7, RF-8, RF-9, RF-10, RF-11, RF-20
      Hecho cuando: tests del cálculo pasan — SPE digit 0 `01/2026`: q1 2026-01-28, q2 corrida desde 2026-02-15 (domingo/feriado) a día hábil; no-SPE 2026-02-15 corrida; sin RIF → vacío; fecha manual no se corrige; `test_compute_due_date_seniat` sigue en verde.

- [x] **T6. Generación automática: `_cron_generate_obligations` (ventana mes actual + próximo), idempotencia, botón "Generar obligaciones" y alerta `calendar_missing`.** RF-4, RF-12, RF-13
      Hecho cuando: un cliente SPE genera 2 quincenas + resto de tipos; correr el cron 2 veces no duplica; año 2027 sin calendario no crea obligaciones y registra una sola alerta `calendar_missing`.

- [ ] **T7. Alertas al contador: destinatario `accountant_id`, CC opcional del cliente, email real con la plantilla existente + link wa.me.** RF-14, RF-15, RF-16
      Hecho cuando: alerta creada con destinatario = partner del contador; con `alert_cc_client` incluye al cliente; el email genera `mail.mail` y marca `state=sent`; contador sin email queda `pending` sin romper el cron.

- [ ] **T8. Seguridad por contador (`security/ir_rule.xml`) + bandeja "Próximos vencimientos" (acción + filtro 30 días).** RF-17, RF-18
      Hecho cuando: `with_user(contador_b)` no ve clientes/obligaciones de `contador_a`; cliente sin `accountant_id` invisible para contadores y visible para admin; el menú abre la bandeja con el filtro de 30 días por defecto.

- [ ] **T9. Wizard "Copiar tabla a otro año" (transient + vista dialog).** RF-3 (HU-4)
      Hecho cuando: copiar a.1 de 2026 a 2027 duplica 120 líneas; intentar copiar sobre un (year, code) existente muestra error de usuario.

- [ ] **T10. Suite de integración en `tests/test_seniat_calendar.py`, demo data y cierre de documentación.** RF-1 – RF-20 (suite completa)
      Hecho cuando: `0 failed` con el conteo Odoo ≥ 121 + tests nuevos; demo manual (admin crea año 2027 copiando tabla, contador ve su bandeja); `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md` y `docs/memory.md` actualizados; `git status` sin archivos inesperados.
