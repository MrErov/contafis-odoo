# 01 - Calendario SENIAT

## Propósito
Calcular la fecha de vencimiento (due_date) de obligaciones fiscales venezolanas según el último dígito del RIF, siguiendo la Providencia SNAT/2025/000091. Permite al contador no depender de tablas públicas cambiantes.

## Alcance
**Incluye:**
- Cálculo de due_date por regla: `1-15`, `primeros_5_dias_habiles`, `ultimo_digito_rif`, `dia_fijo`
- Diccionario `SENIAT_2026_CALENDAR` en `obligation.py` (mes → dígito RIF → día)
- Resolución de mes/año objetivo (`_get_target_month`) considerando periodicidad
- Fallback seguro: regla `1-15` fuera de 2026 retorna `False`

**No incluye:**
- Calendarios SENIAT de años distintos a 2026 (requiere actualización manual)
- Vencimientos IVSS/INCES/BANAVIH (ver spec 02/03/05)

## Modelos involucrados
- `l10n.ve.obligation`: campo `due_date` (computed + inverse), `period`, `obligation_type_id`
- `l10n.ve.obligation.type`: `due_day_rule`, `due_day_value`, `periodicity`
- `l10n.ve.compliance.client`: `rif_last_digit` (computed from RIF)

## Reglas de negocio
1. **Regla `1-15` (SENIAT 2026)**: Día 1-15 según tabla oficial por dígito RIF (0-9). Solo válida para año 2026.
2. **Regla `primeros_5_dias_habiles`**: Primeros 5 días hábiles del mes objetivo (IVSS, BANAVIH).
3. **Regla `ultimo_digito_rif`**: Día = dígito RIF (0→10). Para obligaciones municipales/otras.
4. **Regla `dia_fijo`**: Día fijo configurable (`due_day_value`, máx 28).
5. **Inverso manual**: Si usuario edita `due_date`, se marca `due_date_override=True` y persiste el valor manual.

## Criterios de aceptación (tests)
- `test_compute_due_date_seniat`: valida cálculo para cada dígito RIF (0-9) en meses 1-12 de 2026 usando `SENIAT_2026_CALENDAR`.

## Referencias
- Providencia SNAT/2025/000091 (calendario SENIAT 2026)
- docs/specs/02-gestion-alertas.md (usa due_date para alertas due_soon/overdue)
- docs/specs/05-dashboard-reportes.md (compliance_score usa due_date)
