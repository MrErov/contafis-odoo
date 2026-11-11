# Plan Spec 008-F — Cierre notas reviewer 008-E (retenciones multi-compañía)

## Diagnóstico confirmado

### Nota 1 🔴 — F-A: fuga de company_id en generate_retentions
Archivo: `addons/l10n_ve_compliance_manager/models/retention_service.py`, método `generate_retentions(self, move)` (líneas ~53-59).
El método construye `vals_list` con `partner_id`, `amount`, `currency_id`, `date`, `invoice_id` pero **sin** `company_id`.
Como `company_id` es `required=True` en `l10n.retention` con default `self.env.company`, si el contexto es compañía A y el `move` es de compañía B, la retención queda en A.
Impacto: retenciones de compañía B asignadas erróneamente a compañía A.

### Nota 2 🟡 — F-B: tests negativos faltantes
Los tests de 008-E solo cubren caminos positivos. Faltan:
- `posted` sin `partner_id` → debe fallar (requisito partner).
- `draft` con `partner_id` → debe fallar (requisito posted).
- Secuencia de A no debe usar prefijo `RET-B-` de B (aislamiento bidireccional).

## Fix exacto

### Archivo: `addons/l10n_ve_compliance_manager/models/retention_service.py`
Método: `generate_retentions(self, move)`

**Cambio A1 (defensa en profundidad).** Al inicio del método, inmediatamente tras el chequeo de `move_type`, agregar:

```python
self = self.with_company(move.company_id)
```

**Cambio A2 (company_id explícito).** En cada diccionario `vals` de `vals_list`, agregar:

```python
'company_id': move.company_id.id,
```

### Archivo: `addons/l10n_ve_compliance_manager/tests/test_multi_company_ux.py`
Clase: `TestMultiCompanyUx` (harness existente). Solo se agregan tests; no hay cambio de código de producción para F-B.

**Test T1 — `test_retention_service_propagates_move_company`** (Nota 1)
- Setup: compañía B, partner B, journal B, cuenta gasto B, cuenta pasivo B.
- Crear `account.move` tipo `in_invoice` en B, estado `posted`, partner B.
- Ejecutar `self.env['l10n.ve.retention.service'].with_company(self.company_a).generate_retentions(move_b)` (contexto A, move de B).
- Assert: `retention.company_id == self.company_b` (y != company_a).
- Por qué está en rojo antes del fix: sin `company_id` explícito, el default toma `self.env.company` = A.

**Test T2 — `test_move_resolution_posted_without_partner_fails`** (F-B subtest partner)
- Move `posted` SIN `partner_id` en compañía B.
- Resolver `invoice_id` del move.
- Assert: se levanta `UserError`.
- Por qué rojo: valida el requisito partner de forma independiente (hoy solo validado junto con posted).

**Test T3 — `test_move_resolution_draft_with_partner_fails`** (F-B subtest posted)
- Move `draft` CON `partner_id` válido en compañía B.
- Resolver `invoice_id` del move.
- Assert: se levanta `UserError`.
- Por qué rojo: valida el requisito posted de forma independiente.

**Test T4 — `test_retention_sequence_isolation_bidirectional`** (F-B secuencia)
- Crear secuencia `RET-A-...` para `company_a` y `RET-B-...` para `company_b`.
- Crear retención en A con secuencia de A → assert número empieza con `RET-A-`.
- Crear retención en B con secuencia de B → assert número empieza con `RET-B-`.
- Assert: retención de A NO empieza con `RET-B-`.

## Verificación

Comando targeted (solo `TestMultiCompanyUx`):
```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager:TestMultiCompanyUx
```

Comando suite completa:
```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager 2>&1 | grep -E "odoo.tests.result|FAIL:|ERROR:" | tail -5
```

**Resultado esperado:** `odoo.tests.result: 0 failed, 0 error(s) of N tests` donde N es el conteo oficial de Odoo. El contexto indica `468 tests` (465 + 3 nuevos); si se implementan los 4 tests listados (T1-T4), el conteo real de Odoo es la fuente de verdad (posiblemente 469). Cualquier descenso respecto a 465 es regresión.

**Commit:** `fix(retention): ensure company_id propagation in retention service (Spec 008-F)`. Sin push.

## Restricciones
- Tests primero (rojo), luego fixes.
- No crear archivos temporales (`fix_*.py`, `debug.py`, etc.). Editar directo.
- No tocar fuera de `addons/l10n_ve_compliance_manager/`.
- No reformatear código existente.
- Tests y docstrings en español.
- Cada sub-tarea termina con commit inmediato si los tests pasan.
