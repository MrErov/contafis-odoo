# 01 - Calendario SENIAT

## Propósito
Calcular la fecha de vencimiento (due_date) de obligaciones fiscales venezolanas según el último dígito del RIF, siguiendo la Providencia SNAT/2025/000091 (Gaceta Oficial N° 43.283 del 23-dic-2025). El calendario se administra como datos editables (tablas), no como código.

## Alcance
**Incluye:**
- Modelos `l10n.ve.seniat.calendar.table` (year, code, month_offset) y `l10n.ve.seniat.calendar` (month × rif_digit → day) con constraints de unicidad (`models.Constraint`)
- Precarga 2026: tablas a.1 (vence en el mismo mes) y a.2 (vence en el mes siguiente), 120 líneas cada una (`data/seniat_calendar_2026.xml`, `noupdate="1"`)
- Feriados bancarios (`l10n.ve.bank.holiday`, precarga 2026) y corrimiento al siguiente día hábil bancario
- Cálculo de `due_date`: quincenal SPE vía tabla a.1/a.2, no-SPE día 15 (`dia_fijo`), regla `1-15` legacy vía a.1, `primeros_5_dias_habiles`, `ultimo_digito_rif`
- Generación automática de obligaciones (ventana mes actual + próximo), idempotente, con botón manual "Generar obligaciones"
- Alerta `calendar_missing` cuando falta la tabla del año
- Wizard "Copiar a otro año" para cargar años futuros desde la UI

**No incluye:**
- Precarga de años distintos a 2026 (se copian con el wizard "Copiar a otro año" o se editan a mano)
- Tablas ISLR (est_islr/ret_islr): diferidas; el modelo (`code` + `month_offset`) ya las soporta
- Feriados bancarios de años futuros (editables por UI)

## Modelos involucrados
- `l10n.ve.seniat.calendar.table`: tabla del año (year, code, month_offset, line_ids)
- `l10n.ve.seniat.calendar`: línea month × rif_digit → day
- `l10n.ve.bank.holiday`: feriado bancario (date UNIQUE, year computed stored)
- `l10n.ve.copy.calendar.wizard`: wizard transient de copia de tablas entre años
- `l10n.ve.obligation`: `due_date` (computed + inverse), `period`, `quincena` (monthly/q1/q2)
- `l10n.ve.compliance.client`: `is_spe`, `applicable_type_ids`, `rif_last_digit`
- `l10n.ve.obligation.type`: `seniat_table_code`, `periodicity` (quincenal), `alert_cc_client`

## Reglas de negocio
1. **SPE quincenal**: q1 vence por la tabla a.1 (mes del período); q2 por la tabla a.2 (mes siguiente).
2. **No-SPE / `dia_fijo`**: día 15 del mes objetivo, corrido a día hábil si cae fin de semana o feriado.
3. **Corrimiento**: sábado, domingo o feriado bancario → siguiente día hábil (solo hacia adelante).
4. **Tabla faltante**: no se generan obligaciones y se crea una única alerta `calendar_missing` por año.
5. **Idempotencia**: clave (client, type, period, quincena); correr el cron dos veces no duplica.
6. **Override manual**: editar `due_date` marca `due_date_override=True` y el valor no se corrige automáticamente.

## Criterios de aceptación (tests)
- `TestSeniatCalendarModels` / `TestSeniatCalendar2026Data`: constraints, precarga 2026 vs `SENIAT_2026_CALENDAR` (guardia legacy), edición persistente tras `-u`
- `TestBankHolidayModel` / `TestBankHoliday2026Data`: constraint UNIQUE(date), precarga 2026
- `TestObligationTypeSeniatConfig` / `TestComplianceClientSeniatConfig` / `TestSeniatConfigViews`: configuración SPE y tipos por cliente
- `TestObligationDueDateCalculation`: cálculo por dígito/mes, quincenas, corrimiento, no-SPE, sin RIF, override
- `TestObligationGeneration`: ventana rodante, idempotencia, `calendar_missing`
- `TestAlertNotifications`: destinatarios (contador/CC cliente), email y `wa.me`
- `TestAccountantRecordRules` / `TestDueSoonTray`: visibilidad por contador y bandeja 30 días
- `TestCopyCalendarWizard`: copia 2026→2027 (2 tablas, 240 líneas) y errores de validación
- `TestCalendarIntegration`: flujo end-to-end del contador; el histórico `test_compute_due_date_seniat` (en `test_obligation.py`) sigue en verde

## Referencias
- Providencia SNAT/2025/000091 (calendario SENIAT 2026)
- `specs/003-calendario-seniat/{spec,plan,tasks}.md`
- docs/specs/02-gestion-alertas.md (usa due_date para alertas due_soon/overdue)
- docs/specs/05-dashboard-reportes.md (compliance_score usa due_date)
