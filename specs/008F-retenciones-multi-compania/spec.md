# Spec 008-F — Cierre de notas críticas del reviewer 008-E (retenciones multi-compañía)

**Estado:** completada (commit `9107420`, 469 tests verdes)
**Rama:** `19.0`
**Commit base:** `7771f17` (465 tests verdes, working tree limpio)

## Objetivo
Cerrar las 2 notas críticas del reviewer de Spec 008-E sobre el flujo de retenciones multi-compañía:
- **F-A 🔴:** `retention_service.generate_retentions` crea `l10n.retention` sin `company_id` (fuga de compañía cuando `self.env.company` difiere de `move.company_id`).
- **F-B 🟡:** faltan tests negativos/independientes de resolución de `invoice_id` y de aislamiento bidireccional de secuencias.

## Requisitos (EARS)

**R1 (F-A — company_id explícito).**
Cuando `l10n.ve.retention.service.generate_retentions(move)` se invoque con un `move` cuya compañía difiera de `self.env.company`, el sistema debe crear cada registro `l10n.retention` con `company_id = move.company_id.id`.

**R2 (F-A — defensa en profundidad).**
Cuando se invoque `generate_retentions(move)`, el servicio debe ejecutarse con ámbito `self.with_company(move.company_id)` antes de calcular montos y tasas, para que `calculate_amounts` y `get_rate` operen sobre la compañía de la factura.

**R3 (F-B — requisito partner independiente).**
Cuando un `account.move` esté `posted` y no tenga `partner_id`, la resolución de su `invoice_id` debe levantar `UserError`.

**R4 (F-B — requisito posted independiente).**
Cuando un `account.move` esté `draft` y tenga `partner_id`, la resolución de su `invoice_id` debe levantar `UserError`.

**R5 (F-B — aislamiento de secuencias).**
Cuando se crea una `l10n.retention` usando la secuencia de la compañía X, su número debe comenzar con el prefijo de X y no con el prefijo de otra compañía Y.

## Alcance fuera de este spec
- No se modifica lógica de negocio de retenciones ni el modelo `l10n.retention`.
- No se agregan campos nuevos.
- F-B solo agrega tests; el código de resolución ya existe de 008-E.

## Resultado (implementación)

- Commit `9107420`: en `generate_retentions` se agregó `self = self.with_company(move.company_id)` y `'company_id': move.company_id.id` en cada `vals` de `vals_list`.
- 4 tests entregados en `tests/test_multi_company_ux.py`; suite completa `0 failed, 0 error(s) of 469 tests` (465 base + 4).
- Desvío respecto del plan: `test_retention_sequence_isolation_bidirectional` valida el `company_id` de la retención creada en cada compañía en lugar del prefijo de secuencia. La aserción de prefijo (`RET-B-` en B) ya está cubierta por `test_retention_sequence_respects_company` (008-E); con la secuencia global activa, `next_by_code` no es determinista en el harness de tests.
