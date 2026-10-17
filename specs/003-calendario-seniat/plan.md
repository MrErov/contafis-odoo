# Plan 003 - Calendario SENIAT: vencimientos automáticos por último dígito del RIF

Este plan NO toca código todavía. Traduce el spec 003 (dudas resueltas 2026-10-17) a arquitectura Odoo 19.

## Arquitectura general

```
                    ┌─────────────────────────────┐
                    │ l10n.ve.compliance.client   │
                    │  is_spe, accountant_id,     │
                    │  applicable_type_ids (M2M)  │
                    └──────────────┬──────────────┘
                                   │ 1 cliente × N tipos aplicables
                                   ▼
cron mensual ──► _cron_generate_obligations() ──► l10n.ve.obligation
(0 6 1 * *)       ventana: mes actual + próximo     period (MM/YYYY) + quincena
                                   │                      │
                                   │                      ▼
                                   │            _compute_due_date()
                                   │                      │
                                   │         ┌────────────┴───────────┐
                                   │         │ is_spe + seniat_table  │ no-SPE o legacy
                                   │         ▼                        ▼
                                   │  l10n.ve.seniat.calendar    reglas actuales
                                   │  (year, table, month,       (dia_fijo, 5 días
                                   │   rif_digit) → day          hábiles, etc.)
                                   │         │
                                   │         ▼
                                   │  _shift_to_next_banking_day()
                                   │  ← l10n.ve.bank.holiday (feriados 2026+)
                                   ▼
cron diario ──► _cron_generate_compliance_alerts()
(existente)      recipients = accountant.partner_id (+CC cliente)
                 email real (template existente) + link wa.me
```

Principio: la fecha se **calcula** (y se corre a día hábil bancario), no se escribe a mano; el contador solo revisa.

## Modelos nuevos

### `l10n.ve.seniat.calendar.table` — cabecera de tabla oficial (`models/seniat_calendar.py`)

| Campo | Tipo | Detalle |
|-------|------|---------|
| `name` | Char, compute store | `"2026 — a.1 (1ra quincena)"` |
| `year` | Integer, required | 2026, 2027, … |
| `code` | Selection, required | `a1`, `a2`, `est_islr`, `ret_islr` (ISLR diferida) |
| `month_offset` | Selection, required, default `0` | `0` = mismo mes del período; `1` = mes siguiente |
| `description` | Char | Texto libre del contador |
| `line_ids` | One2many | → `l10n.ve.seniat.calendar` |
| constraint | `models.Constraint` | `UNIQUE(year, code)` |

### `l10n.ve.seniat.calendar` — línea (mes × dígito RIF)

| Campo | Tipo | Detalle |
|-------|------|---------|
| `table_id` | Many2one required | ondelete `cascade` |
| `year` | Integer related stored | de `table_id.year` (searchable) |
| `month` | Integer required | 1–12 |
| `rif_digit` | Integer required | 0–9 |
| `day` | Integer required | 1–31 (se valida contra el mes al calcular) |
| constraint | `models.Constraint` | `UNIQUE(table_id, month, rif_digit)` |

240 líneas para 2026 (2 tablas × 12 meses × 10 dígitos). Editable en UI.

### `l10n.ve.bank.holiday` — feriados bancarios (`models/bank_holiday.py`)

| Campo | Tipo | Detalle |
|-------|------|---------|
| `name` | Char, required | "Carnaval lunes", "Semana Santa", … |
| `date` | Date, required | Fecha del feriado bancario |
| `year` | Integer, compute store | de `date` (searchable, agrupa por año) |
| constraint | `models.Constraint` | `UNIQUE(date)` |

Precarga 2026 con `noupdate="1"` desde fuente oficial (calendario bancario/SUDEBAN); incluye los 8 cruces con vencimientos SENIAT detectados. Editable en UI para años futuros. Si un año no tiene feriados cargados, el corrimiento solo evita fines de semana (degradación segura).

### `l10n.ve.seniat.calendar.copy.wizard` — wizard "Copiar tabla a otro año"

TransientModel con `source_table_id` (M2o) + `target_year` (Integer). `action_copy()` valida que no exista (year, code) y duplica las líneas en lote. Cubre HU-4/RF-3 sin cargar 120 registros a mano.

## Modelos modificados

### `l10n.ve.obligation` (`models/obligation.py`)

1. Campo nuevo `quincena`: Selection `[('monthly','Mensual'), ('q1','1ra quincena (01–15)'), ('q2','2da quincena (16–fin)')]`, default `monthly`. El período sigue `MM/YYYY` (libro de compras/ventas y Planilla 99030 dependen de ese formato).
2. `_resolve_due_date()`: nueva prioridad — si `obligation_type_id.seniat_table_code` ≠ `none`:
   - cliente SPE → `_resolve_due_date_calendar()` (RF-6);
   - cliente no-SPE → `_resolve_day_15()` = día 15 del mes siguiente al período (RF-7, Art. 47 LIVA).
   Ambos resultados pasan por `_shift_to_next_banking_day()` (RF-20). Sin `seniat_table_code`, cae al camino legacy actual sin cambios.
3. La regla legacy `'1-15'` se reimplementa consultando la tabla `a1` del año (mismo resultado que el dict actual para 2026; elimina `SENIAT_2026_CALENDAR` hardcodeado) y también pasa por el corrimiento.
4. Las fechas fijadas manualmente por el contador (escritura directa de `due_date`) no se corrigen (RF-20).
5. Métodos nuevos:
   - `_resolve_due_date_calendar(month, year)` — ver pseudocódigo abajo.
   - `_cron_generate_obligations()` — ventana rodante mes actual + próximo; crea obligaciones idempotentes (RF-12/13) y registra alerta `calendar_missing` cuando falta el año (RF-4).
   - `_generate_for_client(client, year, month)` — genera los tipos aplicables del cliente.
6. `_create_alert()`: destinatarios = partner del `accountant_id`; si `alert_cc_client` del tipo y el cliente no es el contador, se agrega `client.partner_id` (RF-14/15). Sin contador asignado → lista vacía, alerta creada igual (visible solo para administradores).
7. `_send_alert()`: canal email usa la plantilla `email_template_l10n_ve_alert` (`send_mail(..., force_send=False)`), marca `state=sent` + `sent_date`; WhatsApp mantiene `wa.me`. Sin email de destinatario → queda `pending` (no rompe el cron).

### `l10n.ve.obligation.type` (`models/obligation_type.py`)

- `seniat_table_code`: Selection `[('none','No usa calendario'), ('a1','Literal a — tabla a.1 (vence 16–fin del mes)'), ('a2','Literal a — tabla a.2 (vence 01–15 del mes siguiente)'), ('est_islr','Estimadas de ISLR'), ('ret_islr','Retenciones de ISLR')]`, default `none`.
- `periodicity`: nuevo valor `('quincenal','Quincenal')`.
- `alert_cc_client`: Boolean, default False (copia al contacto del cliente).

### `l10n.ve.compliance.client` (`models/compliance_client.py`)

- `is_spe`: Boolean, default False (RF-5).
- `applicable_type_ids`: Many2many `l10n.ve.obligation.type` — tipos que aplican al cliente; insumo de la generación automática (RF-12).
- `action_generate_obligations()`: botón manual que genera mes actual + próximo (onboarding de cliente nuevo a mitad de año).

### `l10n.ve.alert` (`models/alert.py`)

- Nuevo tipo `calendar_missing` ("Calendario faltante") en `alert_type` + `ALERT_TYPE_LABELS`.

## Funciones puras / helpers

| Helper | Firma | Uso |
|--------|-------|-----|
| `_add_months` | `(year, month, n) -> (year, month)` | módulo puro; offset de tablas y mes objetivo |
| `_quincena_table_code` | `(periodicity, table_code, quincena) -> code` | mapeo quincena→tabla: `q1`→`a1`, `q2`→`a2` |
| `_get_calendar_day` | `(env, year, code, month, rif_digit) -> int|False` | lookup `l10n.ve.seniat.calendar` con `search(..., limit=1)` |
| `_is_banking_day` | `(env, date) -> bool` | lunes–viernes y sin feriado cargado |
| `_shift_to_next_banking_day` | `(env, date) -> date` | avanza +1 día hasta un día hábil bancario (máx. ~5 iteraciones) |
| `_last_period_month` | `(periodicity, month) -> bool` | trimestral solo cierra en mes %3==0, anual en 12, bimestral en meses pares |

Se implementan como métodos con parámetros explícitos (sin estado oculto); `_add_months`, `_quincena_table_code` y `_is_banking_day` a nivel de módulo para testear puro.

## Algoritmo en pseudocódigo

### 1. Resolución de vencimiento con calendario + corrimiento

```
_resolve_due_date_calendar(month, year):
    code = _quincena_table_code(periodicity, seniat_table_code, quincena)
    day = _get_calendar_day(year, code, month, client.rif_last_digit)
    si day es False: return False                    # RF-4 lo detecta la generación
    offset = month_offset de la tabla (0 = mismo mes, 1 = siguiente)
    target_y, target_m = _add_months(year, month, offset)
    si day > último día de target_m: return False    # dato corrupto en tabla
    return _shift_to_next_banking_day(date(target_y, target_m, day))

_is_banking_day(d):
    return d.weekday() < 5 and not existe l10n.ve.bank.holiday con date == d

_shift_to_next_banking_day(d):
    mientras not _is_banking_day(d): d += 1 día     # solo avanza, nunca retrocede
    return d
```

### 2. Generación automática (cron mensual, ventana rodante)

```
_cron_generate_obligations():
    today = Date.today()
    para (y, m) en [(today.y, today.m), siguiente_mes(today.y, today.m)]:
        para client en compliance.client (con rif):
            _generate_for_client(client, y, m)

_generate_for_client(client, y, m):
    para otype en client.applicable_type_ids:
        si otype.periodicity == 'quincenal':
            si not client.is_spe: continue            # solo SPE es quincenal
            para q en ('q1','q2'):
                crear_si_no_existe(client, otype, f'{m:02d}/{y}', q)
        elif otype.periodicity == 'event': continue
        elif _last_period_month(otype.periodicity, m):
            crear_si_no_existe(client, otype, f'{m:02d}/{y}', 'monthly')

crear_si_no_existe(client, otype, period, q):
    existe = search([(client), (otype), (period), (quincena=q)])
    si existe: return                                 # RF-13 idempotencia
    ob = create({..., quincena: q})                   # due_date se computa solo
    si otype.seniat_table_code != 'none' y ob.due_date es False:
        ob.unlink()
        crear_alerta_calendar_missing(client, period.year)   # RF-4, dedup por cliente+año
```

### 3. Copiar tabla a otro año (wizard)

```
action_copy():
    si existe table(year=target_year, code=source.code): UserError
    create table nueva con mismo code/month_offset
    create líneas en lote: [(0,0,{month, rif_digit, day}) para cada línea origen]
    return action abriendo la tabla nueva
```

## Interfaz

| Vista | Cambio |
|-------|--------|
| `views/seniat_calendar_views.xml` (nuevo) | List/form de tablas; lista inline editable de líneas agrupada por mes; búsqueda por año/código; botón "Copiar a otro año" (wizard dialog) |
| `views/bank_holiday_views.xml` (nuevo) | List editable de feriados agrupada por año; búsqueda por nombre |
| `views/menu.xml` | Menús nuevos bajo Configuración: "Calendario SENIAT" (seq 30) y "Feriados bancarios" (seq 35); bajo raíz: "Próximos vencimientos" (seq 15) → acción `action_l10n_ve_obligation_due_soon` |
| `views/obligation_views.xml` | Campo `quincena` en list/form (etiquetas "1ra (01–15)"/"2da (16–fin)"/"Mensual"); filtro "Próximos 30 días" `[('due_date','<=', context_today() + relativedelta(days=30))]`; filtros por estado; acción "Próximos vencimientos" con contexto de filtros por defecto |
| `views/compliance_client_views.xml` | `is_spe`, `applicable_type_ids`, botón "Generar obligaciones"; filtro "SPE" |
| `views/obligation_type_views.xml` | `seniat_table_code`, `alert_cc_client`; ayuda que explica cada código |

Convenciones Odoo 19 obligatorias: `<list>`, `invisible=`, `view_mode="list,form"`, `@api.depends` explícito.

## Datos (XML)

| Archivo | Cambio |
|---------|--------|
| `data/seniat_calendar_2026.xml` | Reemplazar el comentario por registros reales `noupdate="1"`: tabla `a1` (offset 0, valores del dict actual) + tabla `a2` (offset 1, valores de la tabla comentada). Sin tablas ISLR en esta fase (diferidas) |
| `data/bank_holidays_2026.xml` (nuevo) | `noupdate="1"`: feriados bancarios 2026 desde fuente oficial (verificar calendario bancario/SUDEBAN), incluyendo los 8 cruces con vencimientos SENIAT (ej. 2026-02-15 domingo → corrimiento; validar con la lista oficial antes de cargar) |
| `data/cron.xml` | Nuevo record `cron_l10n_ve_generate_obligations`: modelo `l10n.ve.obligation`, `model._cron_generate_obligations()`, mensual |
| `demo/demo_data.xml` | Tipo "IVA Mensual" → `periodicity='quincenal'`, `seniat_table_code='a1'`; nuevo tipo IVA no-SPE con `dia_fijo=15`; clientes demo con `is_spe`, `accountant_id` (admin) y `applicable_type_ids` |
| `__manifest__.py` | Registrar `security/ir_rule.xml`, `views/seniat_calendar_views.xml`, `views/bank_holiday_views.xml`; versión `19.0.1.1.0` |

## Seguridad

`security/ir_rule.xml` (nuevo, se carga después de `ir.model.access.csv`):

| Modelo | Grupo | Dominio |
|--------|-------|---------|
| `l10n.ve.compliance.client` | `l10n_ve_compliance_accountant` | `[('accountant_id','=',user.id)]` (los clientes sin contador quedan fuera: solo admin) |
| `l10n.ve.obligation` | idem | `[('client_id.accountant_id','=',user.id)]` |
| `l10n.ve.document` | idem | `[('client_id.accountant_id','=',user.id)]` |
| `l10n.ve.alert` | idem | `[('client_id.accountant_id','=',user.id)]` |
| los 4 anteriores | `base.group_system` | `[(1,'=',1)]` (admin ve todo; las reglas OR entre grupos) |

ACL nuevas en `ir.model.access.csv`: `seniat.calendar.table`, `seniat.calendar`, `bank.holiday` y `copy.wizard` (grupo contador, lectura/escritura total). El catálogo de calendario y feriados es global (no lleva regla por `accountant_id`).

Regla de dirección: reglas restrictivas para el grupo contador + regla allow-all para administradores (evita que el admin quede restringido por pertenecer también al grupo contador). Alternativa descartada: filtrar solo por defecto en vistas (no es seguridad real).

## Estrategia de tests

Comando oficial (fuente única del conteo):

```
docker compose run --rm web odoo -d contea \
  -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

Archivo nuevo `tests/test_seniat_calendar.py` (más ampliaciones puntuales en `test_obligation.py`):

| Test | Cubre |
|------|-------|
| `test_calendar_2026_loaded`: tablas a1/a2 existen con 120 líneas y días spot (digit 0 enero = 28/15) | RF-1, RF-2 |
| `test_calendar_edit_persists`: editar un día, simular upgrade (recargar XML no sobrescribe por `noupdate`) | RF-3 |
| `test_due_date_quincena_q1` / `_q2`: SPE digit 0, `01/2026` → 2026-01-28 (miércoles) / 2026-02-15 domingo → corrido al siguiente día hábil según feriados cargados | RF-9, RF-10, RF-11, RF-20 |
| `test_due_date_no_spe_day_15`: `01/2026` → 2026-02-15 domingo → corrido a día hábil | RF-7, RF-20 |
| `test_due_date_spe_without_rif`: sin dígito → False | RF-8 |
| `test_manual_date_not_shifted`: fecha fijada manualmente no se corrige | RF-20 |
| `test_shift_weekend_only_without_holidays`: año sin feriados → solo evita fines de semana | RF-19, RF-20 |
| `test_bank_holidays_2026_loaded`: precarga presente y sin duplicados | RF-19 |
| `test_generate_creates_quincenas`: un cliente SPE con tipo quincenal genera 2 obligaciones; correr 2 veces no duplica | RF-12, RF-13 |
| `test_generate_missing_calendar_alerts`: año 2027 sin tabla → no crea y registra `calendar_missing` una vez | RF-4 |
| `test_alert_recipients_accountant` / `_cc_client` / `_no_accountant` | RF-14, RF-15 |
| `test_alert_email_sent`: alerta email → `mail.mail` creado y `state=sent`; contador sin email → queda `pending` | RF-16 |
| `test_record_rule_accountant_sees_own`: con `with_user(contador_b)` no ve clientes de `contador_a`; cliente sin contador invisible para contadores y visible para admin | RF-17 |
| `test_due_soon_action`: la acción/filtro "Próximos 30 días" existe y acota por fecha | RF-18 |
| `test_copy_wizard`: duplica 120 líneas y rechaza año existente | RF-3 (HU-4) |

Nota: los valores esperados que caen en fin de semana/feriado se fijan contra la lista oficial de feriados cargada (2026-02-15 es domingo; verificar si el corrimiento atraviesa Carnaval según la lista). Riesgos de regresión vigilados: `test_obligation.py::test_compute_due_date_seniat` (2026-01-28 miércoles y 2026-01-19 lunes: no cambian) y `test_cron_generate_alerts` (alertas sin contador no rompen).

Nota de verificación de sintaxis `models.Constraint` (Odoo 19) contra `odoo/orm/` del contenedor antes de escribir los modelos.

## Cobertura RF ⇄ partes

| Parte | RF |
|-------|----|
| Modelos `seniat.calendar.table/line` + XML 2026 + wizard copia | RF-1, RF-2, RF-3 |
| `calendar_missing` en generación | RF-4 |
| `is_spe` + `_resolve_due_date` (SPE/no-SPE/RIF) | RF-5, RF-6, RF-7, RF-8 |
| `quincena` (`monthly`/`q1`/`q2`) + `_resolve_due_date_calendar` | RF-9, RF-10, RF-11 |
| `_cron_generate_obligations` + `applicable_type_ids` | RF-12, RF-13 |
| `_create_alert`/`_send_alert` + `alert_cc_client` | RF-14, RF-15, RF-16 |
| `security/ir_rule.xml` | RF-17 |
| Acción + filtros "Próximos vencimientos" | RF-18 |
| Modelo `bank.holiday` + XML 2026 + vista | RF-19 |
| `_shift_to_next_banking_day` + tests de corrimiento | RF-20 |

## Decisiones técnicas justificadas

| Decisión | Justificación | Alternativa descartada |
|----------|---------------|------------------------|
| Calendario en BD (tabla + líneas), no dict en código | Editable (constitución #2), multi-año, auditable | Mantener `SENIAT_2026_CALENDAR` (requiere deploy por cada año) |
| `quincena` = Selection `monthly`/`q1`/`q2` en columna aparte; `period` sigue `MM/YYYY` | No rompe parsing ni documentos dependientes (libro de compras/ventas, Planilla 99030) | Period con sufijo `01/2026-1Q` (rompe `_get_computed_due_date`, upserts y la Planilla 99030) |
| `month_offset` en la cabecera de tabla | Absorbe la semántica de cada tabla (IVA difiere al mes siguiente, otras no) sin código nuevo | Hardcodear offset por código (bloquea al admin) |
| Regla no-SPE = día 15 del mes siguiente (LIVA art. 47) | Confirmado con fuentes públicas; el cliente no-SPE igual declara | Aplicar RIF a todos (incorrecto para no-SPE) |
| Feriados bancarios en modelo propio + corrimiento solo hacia adelante | Decisión del usuario: evita pagos en día inhábil; catálogo editable por año; degradación segura sin datos | Fecha oficial tal cual (riesgo de multa); días fijos en código (no soporta años futuros) |
| Corrimiento solo en fechas calculadas (RF-6/RF-7/legacy `1-15`), no en manuales | Respetar la fecha explícita del contador | Corregir también las manuales (pisa decisiones del contador) |
| Solo a.1/a.2 en esta fase (ISLR diferida) | Decisión del usuario; la estructura `code`+`month_offset` ya soporta ISLR | Cargar est_islr/ret_islr sin fuente verificada (datos incorrectos = multa) |
| Cron mensual de ventana rodante (mes + próximo) | Cubre clientes nuevos y el salto de año naturalmente | Generación anual única (clientes nuevos sin obligaciones hasta enero) |
| Destinatario principal `accountant_id`; CC opcional en el tipo; sin contador = visible solo admin | Flujo contador-céntrico y confidencialidad (flujo ordenado de asignación) | Mantener `partner_id` como único destinatario (actual); clientes sin contador visibles para todos |
| Reglas de registro grupo contador + allow-all `base.group_system` | Seguridad real y admin operativo | Solo filtros de vista (no protege nada) |
| Email con `force_send=False` | No depende de SMTP en tests ni en cron | `force_send=True` (falla sin servidor de correo configurado) |
| `models.Constraint` (API Odoo 19) en modelos nuevos | Evita la deuda de `_sql_constraints` deprecado | `_sql_constraints` (más warnings de deuda técnica) |

## Decisiones del usuario (2026-10-17) — sin preguntas abiertas

1. Tablas ISLR: solo a.1/a.2 en esta fase; ISLR diferida (la estructura ya la soporta).
2. Feriados bancarios: corregir al siguiente día hábil bancario, con catálogo editable y precarga 2026 (fuente oficial a verificar al cargar).
3. Quincena: columna aparte (Selection `monthly`/`q1`/`q2`); el período `MM/YYYY` no se toca porque el libro de compras/ventas y la Planilla 99030 dependen de él.
4. Cliente sin `accountant_id`: visible y gestionable solo por administradores, para forzar el flujo de asignación.

Listo para `/sdd-tasks 003-calendario-seniat`. La implementación no arranca hasta confirmar los tasks.

## Archivos afectados (resumen)

Nuevos: `models/seniat_calendar.py`, `models/seniat_calendar_copy_wizard.py`, `models/bank_holiday.py`, `views/seniat_calendar_views.xml`, `views/bank_holiday_views.xml`, `data/bank_holidays_2026.xml`, `security/ir_rule.xml`, `tests/test_seniat_calendar.py`.

Modificados: `models/obligation.py`, `models/obligation_type.py`, `models/compliance_client.py`, `models/alert.py`, `models/__init__.py`, `security/ir.model.access.csv`, `views/menu.xml`, `views/obligation_views.xml`, `views/compliance_client_views.xml`, `views/obligation_type_views.xml`, `data/seniat_calendar_2026.xml`, `data/cron.xml`, `demo/demo_data.xml`, `__manifest__.py`, `tests/test_obligation.py`.

Documentación al cierre: `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md`, `SPEC.md`, `docs/memory.md` (local).
