# Plan 004 - Tablas de ISLR (Estimadas/Anticipos y Retenciones) en el Calendario SENIAT 2026

Spec: `specs/004-tablas-islr/spec.md` · Tareas: `specs/004-tablas-islr/tasks.md`

Este plan traduce el spec 004 (aprobado, duda de días de referencia resuelta) a arquitectura Odoo 19. No toca código todavía.

## Arquitectura general

```
        ┌───────────────────────────────────────┐
        │ l10n.ve.obligation.type               │
        │  seniat_table_code: est_islr/ret_islr │
        │  generation_months: "6,9,12" (nuevo)  │
        └──────────────┬────────────────────────┘
                       │ asignado vía applicable_type_ids
                       ▼
cron mensual ──► _cron_generate_obligations()        [existente, T6 de 003]
(ventana mes actual + próximo)
                       │
                       ▼
        _generate_for_client()                        [modificado]
          ├─ generation_months configurado → genera solo esos meses
          ├─ ret_islr (monthly) → genera cada mes de la ventana
          └─ quincenal/event/periodicity → lógica actual sin cambios
                       │
                       ▼
        _create_obligation_if_missing()               [existente]
          └─ _is_calendar_available()                 [modificado]
               ├─ a1/a2 → solo SPE (sin cambios)
               └─ est_islr/ret_islr → exige tabla del año (SPE o no)
                       │
                       ▼
        _compute_due_date() → _resolve_due_date()     [modificado]
          ├─ est_islr/ret_islr → tabla por RIF sin gate is_spe
          ├─ a1/a2 SPE → tabla; no-SPE → día 15 (sin cambios)
          └─ _shift_to_next_banking_day() (fin de semana/feriado)
```

Principio (constitución #2): los días de referencia son **editables** por el contador; `noupdate="1"` conserva sus correcciones. Los valores cargados se marcan como referencia sujeta a verificación con la Gaceta Oficial.

## Modelos modificados (sin cambios estructurales al calendario)

### `l10n.ve.obligation.type` (`models/obligation_type.py`)

| Campo | Tipo | Detalle |
|-------|------|---------|
| `generation_months` | Char (nuevo) | Meses del año (1–12) separados por coma en que se generan las obligaciones; vacío = usar la periodicidad. Estimadas: `"6,9,12"`. Editable en la vista del tipo. |

### `l10n.ve.obligation` (`models/obligation.py`)

1. `_resolve_due_date()`: las tablas `est_islr`/`ret_islr` se resuelven por calendario **sin depender de `is_spe`** (RF-8, RF-9). `is_spe` queda exclusivo de las tablas a.1/a.2 (quincenas de IVA) y de la regla no-SPE del día 15.

```
_resolve_due_date(month, year, today):
    table_code = obligation_type.seniat_table_code
    si table_code en (False, 'none'): camino legacy (sin cambios)
    si client.is_spe o table_code en ('est_islr', 'ret_islr'):
        return _resolve_due_date_calendar(month, year)
    return _resolve_day_15(month, year)
```

2. `_is_calendar_available()`: exige la tabla del año para `est_islr`/`ret_islr` aunque el cliente no sea SPE (RF-10); a.1/a.2 conservan la regla actual (solo SPE).

```
_is_calendar_available(client, obligation_type, year, quincena):
    table_code = obligation_type.seniat_table_code
    si table_code vacío o 'none': True
    si table_code en ('a1','a2') y not client.is_spe: True
    return bool(tabla (year, code efectivo))
```

3. RF-11 (tabla existe pero falta la fila mes/dígito): `_resolve_due_date_calendar()` ya devuelve `False` cuando no hay día; la obligación queda sin vencimiento y visible (no requiere cambio de código, solo test).

### Helpers (`models/obligation.py`)

| Helper | Firma | Uso |
|--------|-------|-----|
| `_parse_generation_months` | `(value) -> tuple[int, ...] | None` | Parsea `"6,9,12"` → `(6, 9, 12)`; vacío/inválido → `None` (fallback a periodicidad). Puro y testeable. |

## Datos (XML)

| Archivo | Cambio |
|---------|--------|
| `data/islr_calendar_2026.xml` (nuevo) | `noupdate="1"` + comentario "Fechas de referencia sujetas a verificación con la Gaceta Oficial". Tabla `est_islr` (offset 0) con 30 líneas (jun, sep, dic × 10 dígitos) y tabla `ret_islr` (offset 1) con 120 líneas (12 meses × 10 dígitos). Día de referencia = último dígito del RIF + 10 |
| `data/islr_obligation_types.xml` (nuevo) | `noupdate="1"`: tipos "Estimadas de ISLR" (`tax_type='islr'`, `seniat_table_code='est_islr'`, `generation_months="6,9,12"`, `periodicity='monthly'`) y "Retenciones de ISLR" (`tax_type='islr'`, `seniat_table_code='ret_islr'`, `periodicity='monthly'`). Editables, con alertas apagadas por defecto hasta que el contador las configure |
| `__manifest__.py` | Registrar `data/islr_calendar_2026.xml` y `data/islr_obligation_types.xml`; versión `19.0.1.2.0` |

## Interfaz

| Vista | Cambio |
|-------|--------|
| `views/obligation_type_views.xml` | Campo `generation_months` con ayuda ("Meses en que se genera; vacío = periodicidad") |

Sin vistas nuevas: la tabla del calendario ya lista los códigos `est_islr`/`ret_islr` en el Selection y el wizard de copia ya replica todas las tablas del año (RF-14).

## Estrategia de tests

Comando oficial (fuente única del conteo):

```
docker compose run --rm web odoo -d contea \
  -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

Ampliación de `tests/test_seniat_calendar.py` (clases nuevas por tarea):

| Test | Cubre |
|------|-------|
| `test_islr_calendar_2026_tables_loaded` / `_line_counts` / `_reference_day_pattern` / `_marked_as_reference` / `_edit_persists_across_upgrade` | RF-1, RF-2, RF-3 |
| `test_islr_obligation_types_seeded` (código, impuesto, asignable a cliente) y `test_generation_months_field_editable` | RF-4, RF-7 |
| `test_generate_estimadas_only_jun_sep_dic` (12 meses → 3 obligaciones; idempotencia) | RF-5 |
| `test_generate_retenciones_monthly` (ventana → 1 por mes) | RF-6 |
| `test_due_date_islr_without_spe` (no-SPE usa tabla: 03/2026 dígito 0 → 2026-04-10) | RF-8, RF-9 |
| `test_due_date_islr_missing_table` (año 2099 sin tabla → vacío + alerta `calendar_missing` al generar) | RF-10 |
| `test_due_date_islr_missing_row` (tabla existe sin fila mes/dígito → vacío) | RF-11 |
| `test_due_date_islr_shift_weekend` (06/2026 dígito 3 → sábado 13 → lunes 15) | RF-12 |
| `test_alert_flow_reuses_existing` (alerta due_soon de una obligación ISLR creada en el flujo existente) | RF-13 |
| `test_copy_calendar_copies_islr_tables` (wizard 2026→2099 copia est_islr/ret_islr) | RF-14 |

Riesgos de regresión vigilados: suite base de 003 (193 tests), en especial `TestObligationDueDateCalculation` (SPE/no-SPE) y `TestObligationGeneration` (idempotencia, `calendar_missing`).

## Cobertura RF ⇄ partes

| Parte | RF |
|-------|----|
| `data/islr_calendar_2026.xml` + tests T1 | RF-1, RF-2, RF-3 |
| `data/islr_obligation_types.xml` + vista del tipo | RF-4, RF-7 |
| `_generate_for_client` + `_parse_generation_months` | RF-5, RF-6, RF-7 |
| `_resolve_due_date` + `_is_calendar_available` sin gate SPE | RF-8, RF-9, RF-11 |
| Alerta `calendar_missing` extendida a ISLR | RF-10 |
| `_shift_to_next_banking_day` (test ISLR) | RF-12 |
| Flujo de alertas existente (test ISLR) | RF-13 |
| Wizard de copia (test est_islr/ret_islr) | RF-14 |

## Decisiones técnicas justificadas

| Decisión | Justificación | Alternativa descartada |
|----------|---------------|------------------------|
| Meses de generación como campo Char `generation_months` | Editable por el contador (constitución #2); no altera la semántica de `periodicity`; cubre jun/sep/dic sin código nuevo por impuesto | Nueva periodicidad `anticipos_islr` (rígida: cualquier cambio de meses requiere deploy) |
| Día de referencia = dígito del RIF + 10 | Patrón confirmado por el usuario; explícito, uniforme y fácil de corregir cuando llegue la Gaceta | Días oficiales inventados (riesgo de multa); repetir días de a.1 (rango 16-31, poco plausible para retenciones) |
| `noupdate="1"` + descripción "referencia sujeta a verificación" | El contador corrige desde la UI y el upgrade no pisa; la limitación queda visible en el dato y en docs | Bloquear hasta tener Gaceta (retrasa la automatización completa) |
| Tipos de obligación como datos generales (`data/`, `noupdate`) | Deben existir en cualquier instalación para que el contador asigne y el cron genere | Solo demo (en producción el contador tendría que crearlos a mano) |
| `is_spe` queda solo para a.1/a.2 | El ISLR aplica a toda persona jurídica; la elegibilidad es el tipo asignado | Exigir SPE para ISLR (excluiría clientes que sí declaran) |
| Sin cambios al modelo del calendario | `code` + `month_offset` ya soportan las tablas (spec 003 RF-2) | Agregar campos nuevos al calendario (innecesario) |

## Archivos afectados (resumen)

Nuevos: `data/islr_calendar_2026.xml`, `data/islr_obligation_types.xml`.

Modificados: `models/obligation.py`, `models/obligation_type.py`, `views/obligation_type_views.xml`, `__manifest__.py`, `tests/test_seniat_calendar.py`.

Documentación al cierre: `docs/memory.md`, `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md`, `SPEC.md`.
