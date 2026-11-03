# Plan T3 - UI de Confianza, Advertencias y Líneas Extraídas

**Spec:** `specs/007-digitalizacion/spec.md` (RF-06, RF-07, RF-08 · RNF-04)
**Baseline:** `0 failed, 0 error(s) of 378 tests` (commit `92c1f2b`)
**Objetivo:** 378 + 6 = **384 tests**

---

## A. Cambios en modelo (`models/digitize_wizard.py`)

### 1. Nuevo modelo `l10n.ve.digitize.line` (TransientModel hijo)

```python
class DigitizeLine(models.TransientModel):
    _name = 'l10n.ve.digitize.line'
    _description = 'Línea extraída en digitalización'
    _order = 'id'

    wizard_id = fields.Many2one(
        'l10n.ve.digitize.wizard', string='Wizard', required=True, ondelete='cascade'
    )
    description = fields.Char(string='Descripción', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True)
    unit_price = fields.Float(string='Precio Unitario', readonly=True)
    total = fields.Float(string='Total Línea', readonly=True)
```

- Registrar en `models/__init__.py`: `from . import digitize_line`
- ACL en `security/ir.model.access.csv` (patrón wizard: `base.group_user`, `account.group_account_manager`, `l10n_ve_compliance_accountant` con 1,1,1,1)

### 2. Campo One2many en `DigitizeWizard`

```python
digitize_line_ids = fields.One2many(
    'l10n.ve.digitize.line',
    'wizard_id',
    string='Líneas Extraídas',
    readonly=True,
)
```

### 3. Cuatro campos compute en `DigitizeWizard`

```python
# UI de confianza
confidence_pct = fields.Integer(
    string='Confianza (%)', compute='_compute_confidence_pct', readonly=True,
)
has_warnings = fields.Boolean(
    string='Tiene Advertencias', compute='_compute_has_warnings', readonly=True,
)
warnings_text = fields.Text(
    string='Advertencias', compute='_compute_warnings_text', readonly=True,
)

# Alerta de descuadre
total_mismatch = fields.Boolean(
    string='Descuadre de Total', compute='_compute_total_mismatch', readonly=True,
)
```

### 4. Reglas de compute

| Campo | Lógica |
|-------|--------|
| `confidence_pct` | `int(confidence * 100)` (ej: 0.87 → 87) |
| `has_warnings` | `bool(warnings_text)` |
| `warnings_text` | Fusionar `warnings_json` (servicio + local, ya dedup en T2). Formato plano: `"código: mensaje\n"` por cada warning. **Nunca markup/HTML.** |
| `total_mismatch` | `abs(total - (subtotal + iva_amount)) > 0.01`<br>**Nota:** IGTF (`igtf_amount`) es informativo, **NO** entra en el cálculo. Si `iva_amount` ausente → recalcular: `subtotal * (1 + iva_rate)` si `iva_rate` ∈ {0.16, 0.08}, `subtotal` si `iva_rate=0`. |

### 5. En `action_digitize`: recrear líneas

```python
# Dentro de action_digitize, tras merged_warnings:
lines_vals = []
for line in extracted.get('lines') or []:
    if isinstance(line, dict):
        lines_vals.append((0, 0, {
            'description': line.get('description') or '',
            'quantity': float(line.get('quantity') or 0.0),
            'unit_price': float(line.get('unit_price') or 0.0),
            'total': float(line.get('total') or 0.0),
        }))
values['digitize_line_ids'] = lines_vals
```

---

## B. Cambios en vista (`views/digitize_wizard_views.xml`)

### Estructura del grupo "Resultado" (existente, ampliado)

```xml
<group string="Resultado" invisible="state != 'done'">
    <group>
        <field name="detected_document_type" readonly="1"/>
        <field name="confidence_pct" readonly="1"
               widget="progressbar"
               options="{'current_value': 'confidence_pct', 'max_value': 100, 'editable': false}"
               decoration-success="confidence_pct >= 85"
               decoration-warning="confidence_pct >= 60 and confidence_pct < 85"
               decoration-danger="confidence_pct < 60"/>
    </group>

    <!-- 14 campos preview readonly -->
    <group>
        <field name="supplier_name" readonly="1"/>
        <field name="supplier_rif" readonly="1"/>
        <field name="invoice_number" readonly="1"/>
        <field name="control_number" readonly="1"/>
        <field name="invoice_date" readonly="1"/>
        <field name="due_date" readonly="1"/>
        <field name="currency_code" readonly="1"/>
        <field name="subtotal" readonly="1"/>
        <field name="iva_rate" readonly="1"/>
        <field name="iva_amount" readonly="1"/>
        <field name="igtf_amount" readonly="1"/>
        <field name="total" readonly="1"/>
        <field name="credit_note_ref" readonly="1" invisible="not credit_note_ref"/>
        <field name="debit_note_ref" readonly="1" invisible="not debit_note_ref"/>
    </group>

    <!-- Bloque advertencias: solo si has_warnings -->
    <div invisible="not has_warnings" class="alert alert-warning" role="alert">
        <field name="warnings_text" readonly="1" nolabel="1"/>
    </div>

    <!-- Tabla líneas One2many readonly -->
    <field name="digitize_line_ids" invisible="not digitize_line_ids" readonly="1">
        <list>
            <field name="description"/>
            <field name="quantity"/>
            <field name="unit_price"/>
            <field name="total"/>
        </list>
    </field>

    <!-- Alerta descuadre: no bloqueante -->
    <div class="alert alert-info" role="alert"
         invisible="not total_mismatch">
        ⚠️ El total extraído no coincide con subtotal + IVA. Revise los importes antes de continuar.
    </div>
</group>
```

### Botones en header (estado `done`)

```xml
<header>
    <button name="action_digitize" string="Analizar"
            type="object" class="btn-primary" invisible="state == 'done'"/>
    <button name="action_apply_to_invoice" string="Usar datos en Factura Física Rápida"
            type="object" class="btn-primary" invisible="state != 'done'"/>
    <button name="action_digitize" string="Reanalizar"
            type="object" class="btn-secondary" invisible="state != 'done'"/>
    <button string="Cancelar" class="btn-secondary" special="cancel"/>
</header>
```

---

## C. Archivos a modificar/crear

| Archivo | Acción |
|---------|--------|
| `models/digitize_wizard.py` | + `DigitizeLine`, + 4 computes, + lógica líneas en `action_digitize` |
| `models/digitize_line.py` | **Nuevo** (modelo hijo) |
| `models/__init__.py` | `from . import digitize_line` |
| `views/digitize_wizard_views.xml` | Vista completa con todos los elementos arriba |
| `security/ir.model.access.csv` | 3 líneas ACL para `l10n.ve.digitize.line` |
| `tests/test_digitize_wizard.py` | Nueva clase `TestDigitizeWarningsUi` con 6 tests |

---

## D. Tests nuevos (`TestDigitizeWarningsUi`)

```python
@tagged('post_install', '-at_install')
class TestDigitizeWarningsUi(DigitizeTestMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    def test_warnings_text_lists_every_code(self):
        """Los 6 códigos del contrato aparecen en warnings_text."""
        payload = {
            'document_type': 'factura_z',
            'confidence': 0.87,
            'extracted': {'supplier_name': 'Test'},
            'warnings': [
                {'code': 'low_confidence', 'message': 'msg1', 'field': 'control_number'},
                {'code': 'invalid_rif', 'message': 'msg2', 'field': 'supplier_rif'},
                {'code': 'amount_mismatch', 'message': 'msg3', 'field': 'total'},
                {'code': 'missing_field', 'message': 'msg4', 'field': 'invoice_date'},
                {'code': 'unknown_document_type', 'message': 'msg5', 'field': None},
                {'code': 'parsing_error', 'message': 'msg6', 'field': 'subtotal'},
            ],
        }
        wizard = self._done_wizard(payload)
        text = wizard.warnings_text
        for code in ('low_confidence', 'invalid_rif', 'amount_mismatch',
                     'missing_field', 'unknown_document_type', 'parsing_error'):
            self.assertIn(f'{code}:', text)

    def test_has_warnings_flag(self):
        """has_warnings = True cuando hay warnings; False cuando no."""
        wizard = self._done_wizard()  # fixture sin warnings
        self.assertFalse(wizard.has_warnings)

        payload = _load_fixture()
        payload['warnings'] = [{'code': 'missing_field', 'field': 'supplier_rif', 'message': 'Falta RIF'}]
        wizard = self._done_wizard(payload)
        self.assertTrue(wizard.has_warnings)

    def test_low_confidence_threshold_flag(self):
        """confidence_pct y decoración: 0.87→87%(alta), 0.6→60%(media), 0.5→50%(baja)."""
        w1 = self._done_wizard({'confidence': 0.87})
        self.assertEqual(w1.confidence_pct, 87)

        w2 = self._done_wizard({'confidence': 0.60})
        self.assertEqual(w2.confidence_pct, 60)

        w3 = self._done_wizard({'confidence': 0.50})
        self.assertEqual(w3.confidence_pct, 50)

    def test_line_preview_rows_created(self):
        """Dos líneas en la respuesta → dos registros digitize_line_ids."""
        payload = _load_fixture()  # tiene 2 líneas
        wizard = self._done_wizard(payload)
        self.assertEqual(len(wizard.digitize_line_ids), 2)
        self.assertEqual(wizard.digitize_line_ids[0].description, 'Servicio de consultoría')
        self.assertEqual(wizard.digitize_line_ids[1].quantity, 2)

    def test_total_mismatch_flag_true_when_difference(self):
        """total_mismatch = True cuando total ≠ subtotal + iva_amount (tolerancia 0.01)."""
        # Caso OK: 1000 + 160 = 1160
        wizard = self._done_wizard()
        self.assertFalse(wizard.total_mismatch)

        # Caso descuadre: 1000 + 160 ≠ 1200
        payload = _load_fixture()
        payload['extracted']['total'] = 1200.0
        wizard = self._done_wizard(payload)
        self.assertTrue(wizard.total_mismatch)

        # IGTF NO cuenta para mismatch: 1000 + 160 + 30(IGTF) = 1190 ≠ 1160 → mismatch por IGTF no debe activarse
        payload = _load_fixture()
        payload['extracted']['igtf_amount'] = 30.0
        payload['extracted']['total'] = 1190.0  # subtotal + iva + igtf
        wizard = self._done_wizard(payload)
        self.assertFalse(wizard.total_mismatch)

    def test_warning_text_is_plain_text(self):
        """warnings_text no contiene markup HTML (ni < ni > sin escapar)."""
        payload = {
            'document_type': 'factura_z',
            'confidence': 0.87,
            'extracted': {'supplier_name': 'Test'},
            'warnings': [
                {'code': 'low_confidence', 'message': '<script>alert(1)</script>', 'field': 'x'},
            ],
        }
        wizard = self._done_wizard(payload)
        text = wizard.warnings_text
        self.assertNotIn('<', text)
        self.assertNotIn('>', text)
        self.assertIn('low_confidence:', text)
```

---

## E. Riesgos y decisiones resueltas

| Tema | Decisión |
|------|----------|
| **Cálculo `total_mismatch`** | Usar `subtotal + iva_amount` (del servicio). Si `iva_amount` ausente pero `iva_rate` conocido: `subtotal * (1 + iva_rate)` para 0.16/0.08; `subtotal` para 0.0. IGTF **excluido** del cálculo (solo informativo). |
| **`warnings_text`** | Fusionar servicio + local (ya hecho en T2 con `_merge_warnings`, servicio gana). Formato: `"código: mensaje\n"` por warning. Texto plano. |
| **Vista progressbar** | Usar `widget="progressbar"` con `decoration-*` para indicador visual (Odoo 19 nativo). No JS custom. |
| **T4 no invadido** | `digitized_document_type`, `digitize_confidence`, `digitized_document_ref` son del wizard físico → T4. T3 solo muestra `detected_document_type` y `confidence_pct`. |

---

## F. Verificación

```bash
# 1. Actualizar módulo
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --stop-after-init --workers 0

# 2. Correr tests
docker compose run --rm web odoo -d contea \
  -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager

# 3. Verificar: 0 failed, 0 error(s) of 384 tests
```

---

## G. Entregable del planner

Este documento (`t3_plan.md`) sirve como especificación completa para el **implementer**. El implementer:
1. Lee este plan
2. Ejecuta los cambios en el orden: modelo → vista → tests
3. Corre los tests y confirma `384`
4. Commitea con mensaje `feat(spec-007): T3 UI confianza/advertencias/líneas`
