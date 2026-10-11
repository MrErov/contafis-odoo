# Plan 001 - Backend Odoo-First: Cargar facturas, generar libro y asientos

## Archivos a crear / modificar

### Modelos existentes (extensión con `_inherit`)

| Archivo | Responsabilidad | RFs |
|---------|-----------------|-----|
| `addons/l10n_ve_compliance_manager/models/vat_book_line.py` | Extender `vat.book.line`: campos `source`, `account_move_id`, `modified_by`, `modified_at`, `is_manually_modified` + método `_get_operation_code()` | RF-2, RF-9, RF-10, RF-12 |
| `addons/l10n_ve_compliance_manager/models/account_move.py` | Extender `account.move`: `_generate_vat_book_line()`, override `_post()`, override `button_draft()`, campo `l10n_ve_control_number` | RF-2, RF-3, RF-8, RF-16 |
| `addons/l10n_ve_compliance_manager/models/account_tax.py` | Extender `account.tax`: campo `l10n_ve_tax_type` (Selection) | RF-15 |
| `addons/l10n_ve_compliance_manager/models/__init__.py` | Exportar nuevos modelos | — |

### Nuevo modelo: Wizard de factura física

| Archivo | Responsabilidad | RFs |
|---------|-----------------|-----|
| `addons/l10n_ve_compliance_manager/models/physical_invoice_wizard.py` | Modelo transitorio `l10n.ve.physical.invoice.wizard`: campos, validaciones, creación de `account.move` + partner | RF-1, RF-4, RF-5, RF-6, RF-7, RF-13 |
| `addons/l10n_ve_compliance_manager/models/regenerate_confirm_wizard.py` | Modelo transitorio `l10n.ve.regenerate.confirm.wizard`: diálogo confirmación regenerar libro (botón Confirmar/Cancelar) | RF-14 |

### Vistas XML

| Archivo | Responsabilidad | RFs |
|---------|-----------------|-----|
| `addons/l10n_ve_compliance_manager/views/vat_book_line_views.xml` | Tree/form: mostrar `source`, `account_move_id`, campos auditoría | RF-9, RF-10 |
| `addons/l10n_ve_compliance_manager/views/account_move_views.xml` | Botón "Regenerar libro" en form view (invisible si state != 'posted') | RF-3 |
| `addons/l10n_ve_compliance_manager/views/physical_invoice_wizard_views.xml` | Wizard form: 4 secciones, selector tipo, botón "Crear y Postear" | RF-1, RF-7, RF-13 |

### Tests

| Archivo | Responsabilidad | RFs |
|---------|-----------------|-----|
| `addons/l10n_ve_compliance_manager/data/ir_model_access.csv` | ACLs para wizard (base.user_admin) | — |
| `addons/l10n_ve_compliance_manager/__manifest__.py` | Añadir dependencias, modelos, vistas, data; declara `post_init_hook` | — |
| `addons/l10n_ve_compliance_manager/hooks/post_init_hook.py` | `post_init_hook`: UPDATE vat_book_line SET source='excel_import' WHERE source IS NULL | RF-9 |

### Tests

| Archivo | Responsabilidad | RFs |
|---------|-----------------|-----|
| `addons/l10n_ve_compliance_manager/tests/test_physical_invoice_wizard.py` | Tests wizard: creación, validaciones, partner, post | RF-1, RF-4, RF-5, RF-6, RF-7, RF-13 |
| `addons/l10n_ve_compliance_manager/tests/test_vat_book_line_sync.py` | Tests sincronización: post, regenerar, button_draft, multi-base | RF-2, RF-3, RF-8, RF-10, RF-14 |
| `addons/l10n_ve_compliance_manager/tests/test_vat_book_line_fields.py` | Tests campos nuevos: source, auditoría, operation_code | RF-9, RF-12 |
| `addons/l10n_ve_compliance_manager/tests/test_export_regression.py` | Tests regresión export XLSX/PDF con líneas odoo_invoice | RF-11 |
| `addons/l10n_ve_compliance_manager/tests/test_regenerate_confirm_wizard.py` | Tests wizard confirmación regenerar: abrir, confirmar, cancelar | RF-14 |

---

## Funciones puras necesarias

### `vat_book_line.py`

```python
# RF-12: Helper compartido para operation_code (mapping REAL de import_wizard.py)
@api.model
def _get_operation_code(self, rate_type: str, book_type: str) -> str:
    """
    rate_type: 'import', 'general', 'reduced', 'no_credit', 'not_subject', 'non_contrib'
    book_type: 'purchase', 'sale'
    Retorna código SENIAT según planilla 99030.
    """
    if book_type == 'purchase':
        if rate_type == 'import':
            return '31'
        elif rate_type == 'general':
            return '33'
        elif rate_type == 'reduced':
            return '333'
        else:  # no_credit, not_subject
            return '30'
    else:  # sale
        if rate_type in ('general', 'non_contrib'):
            return '42'
        else:  # not_subject, not_taxed
            return '40'
```

### `physical_invoice_wizard.py`

```python
# RF-1: Campo currency_id para widget monetary
currency_id = fields.Many2one(
    'res.currency',
    default=lambda self: self.env.company.currency_id,
    required=True,
)

# RF-4: Validación RIF módulo 11 (reutilizar validador existente)
def _validate_rif_module_11(self, rif: str) -> bool:
    """Valida dígito de control RIF venezolano. Reusa método de vat.book.line o import_wizard."""

# RF-5: Crear partner desde RIF
def _create_partner_from_rif(self, rif: str, name: str, partner_type: str) -> res.partner:
    """Crea res.partner con vat=rif, company_type según partner_type ('person'/'company')."""

# RF-1: Construir líneas de account.move desde bases del wizard
def _build_move_lines_from_bases(self, wizard_data: dict) -> list[Command]:
    """
    Input: dict con base_general, base_reduced, base_not_subject, base_not_taxed, base_no_credit,
           tax_ids correspondientes, account_id, partner_id, type (purchase/sale)
    Output: lista de Command.create para account.move.line
    """
    lines = []
    # 1. Línea base general 16% → tax_id IVA General 16%
    # 2. Línea base reducida 8% → tax_id IVA Reducida 8%
    # 3. Línea base adicional → tax_id IVA Adicional
    # 4. Línea no sujeta → sin tax
    # 5. Línea no gravada → sin tax
    # 6. Línea sin crédito → tax_id IVA No Crédito (account_id = cuenta gasto)
    # 7. Línea CxP/CxC → account_id partner payable/receivable
    return lines

# RF-1: Acción principal
def action_create_and_post(self) -> dict:
    """Valida, crea account.move, postea, retorna acción para abrir factura."""
```

### `account_move.py`

```python
# RF-2: Sincronización principal
def _generate_vat_book_line(self) -> Recordset:
    """
    Para cada account.move.line con tax_ids:
      - Determina rate_type desde tax.tax_group_id o tax_id
      - book_type = 'purchase' si in_invoice/in_refund, 'sale' si out_invoice/out_refund
      - operation_code = self.env['vat.book.line']._get_operation_code(rate_type, book_type)
      - Crea vat.book.line con base_*/vat_*, source='odoo_invoice', account_move_id=self.id
    """

# RF-2, RF-14: Override _post
def _post(self, soft=True):
    res = super()._post(soft)
    for move in self.filtered(lambda m: m.move_type in ('in_invoice', 'out_invoice')):
        # Check is_manually_modified → confirm dialog handled in UI via button
        move._generate_vat_book_line()
    return res

# RF-8: Override button_draft
def button_draft(self):
    res = super().button_draft()
    self.env['vat.book.line'].search([
        ('account_move_id', 'in', self.ids),
        ('source', '=', 'odoo_invoice')
    ]).unlink()
    return res

# RF-3, RF-14: Botón regenerar
def action_regenerate_vat_book_line(self):
    """Llamado desde botón en form view. Solo si state='posted'."""
    self.ensure_one()
    if self.state != 'posted':
        raise UserError(_('Solo facturas posteadas pueden regenerar el libro.'))

    # RF-14: Verificar si hay líneas editadas manualmente
    manual_lines = self.env['vat.book.line'].search([
        ('account_move_id', '=', self.id),
        ('source', '=', 'odoo_invoice'),
        ('is_manually_modified', '=', True)
    ])
    if manual_lines:
        # Abrir wizard de confirmación
        return {
            'name': _('Confirmar Regeneración'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.ve.regenerate.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    # Sin ediciones manuales → regenerar directo
    self._generate_vat_book_line()
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'type': 'success',
            'message': _('Líneas del libro regeneradas: %d') % len(self.vat_book_line_ids),
        }
    }
```

---

## Algoritmos en pseudocódigo

### `_generate_vat_book_line()` — RF-2

```
FUNCTION _generate_vat_book_line(move: account.move):
    # (a) Verificar ediciones manuales
    manual_lines = search vat.book.line WHERE
        account_move_id = move.id
        AND source = 'odoo_invoice'
        AND is_manually_modified = True
    IF manual_lines NOT EMPTY:
        RETURN confirmation_required(manual_lines)

    # (b) Borrar líneas odoo_invoice existentes
    DELETE vat.book.line WHERE
        account_move_id = move.id
        AND source = 'odoo_invoice'

    # (c) Derivar nuevas líneas
    book_type = 'purchase' IF move.move_type in ('in_invoice', 'in_refund') ELSE 'sale'
    FOR EACH line IN move.line_ids WHERE line.tax_ids NOT EMPTY:
        FOR EACH tax IN line.tax_ids:
            rate_type = _map_tax_to_rate_type(tax)
            IF rate_type IS NULL: CONTINUE

            base = line.price_subtotal
            vat = tax.amount * base / 100  # Odoo ya calcula en tax lines

            operation_code = vat.book.line._get_operation_code(rate_type, book_type)

            CREATE vat.book.line {
                account_move_id: move.id,
                source: 'odoo_invoice',
                book_type: book_type,
                operation_code: operation_code,
                partner_id: move.partner_id.id,
                invoice_number: move.name,
                invoice_date: move.invoice_date,
                # Asignar a campo correspondiente según rate_type:
                base_general: base IF rate_type='general' ELSE 0,
                vat_general: vat IF rate_type='general' ELSE 0,
                base_reduced: base IF rate_type='reduced' ELSE 0,
                vat_reduced: vat IF rate_type='reduced' ELSE 0,
                base_additional: base IF rate_type='additional' ELSE 0,
                vat_additional: vat IF rate_type='additional' ELSE 0,
                base_not_subject: base IF rate_type='not_subject' ELSE 0,
                base_not_taxed: base IF rate_type='exempt' ELSE 0,
                base_no_credit: base IF rate_type='no_credit' ELSE 0,
            }

FUNCTION _map_tax_to_rate_type(tax: account.tax) -> str:
    IF tax.l10n_ve_tax_type == 'general': RETURN 'general'
    IF tax.l10n_ve_tax_type == 'reduced': RETURN 'reduced'
    IF tax.l10n_ve_tax_type == 'additional': RETURN 'additional'
    IF tax.l10n_ve_tax_type == 'no_credit': RETURN 'no_credit'
    IF tax.l10n_ve_tax_type == 'exempt': RETURN 'exempt'
    IF tax.l10n_ve_tax_type == 'not_subject': RETURN 'not_subject'
    RETURN NULL
```

### Wizard `action_create_and_post()` — RF-1, RF-4, RF-5, RF-7, RF-13

```
FUNCTION action_create_and_post(wizard):
    # Validaciones
    IF all bases == 0: RAISE ValidationError("Al menos una base > 0 requerida")
    IF any base < 0: RAISE ValidationError("Bases no pueden ser negativas")

    # RF-4, RF-5: RIF → partner
    rif = wizard.partner_vat
    IF NOT _validate_rif_module_11(rif):
        RAISE ValidationError("RIF inválido (dígito de control)")

    partner = search res.partner WHERE vat = rif AND company_id = env.company
    IF NOT partner:
        # Inline creation data from wizard
        partner = _create_partner_from_rif(rif, wizard.partner_name, wizard.partner_type)

    # RF-7: Defaults según tipo
    journal = _get_default_journal(wizard.type)
    account = _get_default_account(wizard.type)
    taxes = _get_taxes_for_bases(wizard)  # Mapea cada base a su tax_id

    # RF-13: Total físico (solo informativo)
    computed_total = sum(bases) + sum(vats)
    IF wizard.physical_total AND wizard.physical_total != computed_total:
        WARNING "Total físico no cuadra. Revise las bases."

    # Construir líneas
    move_lines = _build_move_lines_from_bases({
        'partner_id': partner.id,
        'journal_id': journal.id,
        'account_id': account.id,
        'taxes': taxes,
        'bases': wizard.bases_dict,
        'type': wizard.type,
        'concept': wizard.concept,
        'control_number': wizard.control_number,
    })

    # Crear y postear
    move = CREATE account.move {
        move_type: 'in_invoice' IF wizard.type='purchase' ELSE 'out_invoice',
        partner_id: partner.id,
        journal_id: journal.id,
        invoice_date: wizard.invoice_date,
        invoice_date_due: wizard.invoice_date_due,
        ref: wizard.control_number,
        narration: wizard.concept,
        line_ids: move_lines,
    }
    move.action_post()  # Dispara _generate_vat_book_line() via _post override

    RETURN action to open move.form view
```

---

## Interfaz (XML)

### Wizard `l10n.ve.physical.invoice.wizard` — Form View

```xml
<form string="Factura Física Rápida">
  <header>
    <button name="action_create_and_post" string="Crear y Postear" type="object" class="btn-primary"/>
    <button string="Cancelar" class="btn-secondary" special="cancel"/>
  </header>
  <sheet>
    <group string="1. Identificación">
      <field name="type" widget="radio"/>  <!-- purchase/sale -->
      <field name="partner_vat" placeholder="RIF (J-12345678-9)"/>
      <field name="partner_name" readonly="1" invisible="partner_id == False"/>
      <field name="partner_id" invisible="1"/>
      <!-- Sección "Nuevo partner" expandible si partner_id no existe -->
      <field name="new_partner_name" invisible="partner_id != False"/>
      <field name="new_partner_type" invisible="partner_id != False"/>
      <field name="new_partner_street" invisible="partner_id != False"/>
      <field name="new_partner_email" invisible="partner_id != False"/>
      <field name="new_partner_phone" invisible="partner_id != False"/>
      <field name="invoice_number"/>
      <field name="control_number"/>
      <field name="invoice_date"/>
    </group>
    <group string="2. Bases e IVA">
      <field name="base_general" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="vat_general" readonly="1" widget="monetary"/>
      <field name="base_reduced" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="vat_reduced" readonly="1" widget="monetary"/>
      <field name="base_additional" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="vat_additional" readonly="1" widget="monetary"/>
      <field name="base_not_subject" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="base_not_taxed" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="base_no_credit" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="vat_no_credit" readonly="1" widget="monetary"/>
    </group>
    <group string="3. Retención (opcional)">
      <field name="retention_number"/>
      <field name="retention_vat" widget="monetary" options="{'currency_field': 'currency_id'}"/>
      <field name="retention_direction" widget="selection"/>
    </group>
    <group string="4. Otros">
      <field name="concept"/>
      <field name="physical_total" widget="monetary" readonly="1" help="Total según factura física (solo informativo)"/>
      <field name="computed_total" widget="monetary" readonly="1" help="Calculado: sum(bases) + sum(IVAs)"/>
    </group>
  </sheet>
</form>
```

### `account.move` Form View — Botón Regenerar

```xml
<record id="view_account_move_form_inherit_vat_book" model="ir.ui.view">
  <field name="model">account.move</field>
  <field name="inherit_id" ref="account.view_move_form"/>
  <field name="arch" type="xml">
    <xpath expr="//header/button[@name='action_post']" position="after">
      <button name="action_regenerate_vat_book_line"
              string="Regenerar Libro"
              type="object"
              class="btn-secondary"
              invisible="state != 'posted' or move_type not in ('in_invoice','out_invoice')"/>
    </xpath>
  </field>
</record>
```

### `vat.book.line` Tree/Form — Campos nuevos

```xml
<record id="view_vat_book_line_tree_inherit" model="ir.ui.view">
  <field name="model">vat.book.line</field>
  <field name="inherit_id" ref="l10n_ve_compliance_manager.view_vat_book_line_tree"/>
  <field name="arch" type="xml">
    <xpath expr="//field[@name='book_type']" position="after">
      <field name="source" invisible="1"/>
      <field name="account_move_id" invisible="1"/>
      <field name="is_manually_modified" invisible="1"/>
    </xpath>
  </field>
</record>

<record id="view_vat_book_line_form_inherit" model="ir.ui.view">
  <field name="model">vat.book.line</field>
  <field name="inherit_id" ref="l10n_ve_compliance_manager.view_vat_book_line_form"/>
  <field name="arch" type="xml">
    <xpath expr="//field[@name='base_no_credit']" position="after">
      <separator string="Trazabilidad"/>
      <field name="source" readonly="1"/>
      <field name="account_move_id" readonly="1"/>
      <field name="modified_by" readonly="1"/>
      <field name="modified_at" readonly="1"/>
      <field name="is_manually_modified" readonly="1"/>
    </xpath>
  </field>
</record>
```

### Wizard `l10n.ve.regenerate.confirm.wizard` — Form View

```xml
<record id="view_regenerate_confirm_wizard_form" model="ir.ui.view">
  <field name="model">l10n.ve.regenerate.confirm.wizard</field>
  <field name="arch" type="xml">
    <form string="Confirmar Regeneración del Libro">
      <sheet>
        <group>
          <label string="Hay líneas editadas manualmente que se perderán. ¿Desea continuar?"/>
        </group>
      </sheet>
      <footer>
        <button name="action_confirm" string="Confirmar" type="object" class="btn-primary"/>
        <button string="Cancelar" class="btn-secondary" special="cancel"/>
      </footer>
    </form>
  </field>
</record>
```

---

## Decisiones técnicas justificadas

| Decisión | Justificación | Alternativa descartada |
|----------|---------------|------------------------|
| Override `_post()` en `account.move` para sincronizar | Inmediatez, atomicidad con transacción del post, Constitution #1 (extender Odoo) | Server action / cron (desacoplado, latencia, riesgo de desincronización) |
| Wizard crea `account.move` real (no modelo intermedio) | Constitution #1: Odoo como única fuente de verdad; asientos reales para conciliación | Modelo ligero tipo `l10n.ve.invoice.draft` (reimplementa contabilidad) |
| `is_manually_modified` computed stored + `modified_by`/`modified_at` | Constitution #2: trazabilidad editable; RF-14 necesita detectar ediciones manuales | Solo `write_date`/`write_uid` (no distingue edición manual vs automática) |
| `_get_operation_code()` @api.model en `vat.book.line` | Stateless, compartido entre import_wizard y sync, reusable | Función módulo global (no testeable, no overridable) |
| `source` Selection en `vat.book.line` | Discrimina origen para export, regeneración, auditoría | Campo Char libre (sin constraint, propenso a typos) |
| Migración `post_init_hook` en `hooks/post_init_hook.py` set `source='excel_import'` | Datos existentes conservan semántica; no rompe exports; hook estándar Odoo | `pre-migration.py` en carpeta migrations (no es el patrón estándar para esto) |
| Wizard valida RIF módulo 11 inline | UX: feedback inmediato sin round-trip servidor | Validación solo en create (error tardío) |
| Botón "Regenerar libro" sin `confirm`; wizard de confirmación `l10n.ve.regenerate.confirm.wizard` si hay ediciones manuales | RF-14 requiere detectar `is_manually_modified`; UX nativa Odoo con wizard TransientModel | `confirm` attribute en XML (no permite lógica condicional) |

---

## Estrategia de tests

### Comando de ejecución
```bash
docker compose run --rm web odoo -d contea \
  -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

### Tests por archivo (15 nuevos)

#### `test_physical_invoice_wizard.py` (5 tests)
| Test | RFs | Qué verifica |
|------|-----|--------------|
| `test_wizard_create_purchase_invoice` | RF-1, RF-7 | Crea factura compra, postea, genera vat.book.line |
| `test_wizard_create_sale_invoice` | RF-1, RF-7 | Crea factura venta, defaults correctos (journal, account, tax) |
| `test_wizard_validates_rif_module_11` | RF-4 | RIF inválido → ValidationError; RIF válido → OK |
| `test_wizard_creates_partner_inline` | RF-5 | RIF nuevo → crea partner con vat, company_type correcto |
| `test_wizard_physical_total_warning` | RF-13 | Total físico ≠ calculado → warning (no bloquea) |

#### `test_vat_book_line_sync.py` (4 tests)
| Test | RFs | Qué verifica |
|------|-----|--------------|
| `test_post_invoice_generates_vat_book_line` | RF-2 | Post factura → vat.book.line con source='odoo_invoice' |
| `test_regenerate_button_updates_lines` | RF-3 | Editar factura → regenerar → líneas actualizadas + toast |
| `test_button_draft_deletes_odoo_lines` | RF-8 | button_draft → borra solo source='odoo_invoice' |
| `test_multi_base_invoice_creates_multiple_lines` | RF-10 | Base general + reducida → 2 vat.book.line mismo account_move_id |

#### `test_vat_book_line_fields.py` (4 tests)
| Test | RFs | Qué verifica |
|------|-----|--------------|
| `test_source_and_audit_fields` | RF-9 | Campos source, account_move_id, modified_by, modified_at, is_manually_modified existen y funcionan |
| `test_get_operation_code_helper` | RF-12 | `_get_operation_code(rate, book_type)` retorna códigos SENIAT correctos |
| `test_account_tax_l10n_ve_type_field` | RF-15 | account.tax tiene l10n_ve_tax_type Selection con valores correctos |
| `test_account_move_control_number_field` | RF-16 | account.move tiene l10n_ve_control_number Char y wizard lo completa |

#### `test_export_regression.py` (1 test)
| Test | RFs | Qué verifica |
|------|-----|--------------|
| `test_export_xlsx_includes_odoo_lines` | RF-11 | Export vat.book.line XLSX incluye líneas source='odoo_invoice' y totales cuadran |

#### `test_regenerate_confirm_wizard.py` (1 test)
| Test | RFs | Qué verifica |
|------|-----|--------------|
| `test_regenerate_confirm_wizard_flow` | RF-14 | Wizard se abre si hay ediciones manuales; confirmar → regenera; cancelar → no regenera |

---

## Cobertura RF → Implementación

| RF | Archivo(s) | Función/Método | Test |
|----|------------|----------------|------|
| RF-1 | `physical_invoice_wizard.py`, views | `action_create_and_post()`, `_build_move_lines_from_bases()` | `test_wizard_create_purchase_invoice` |
| RF-2 | `account_move.py`, `vat_book_line.py` | `_generate_vat_book_line()`, `_map_tax_to_rate_type()` | `test_post_invoice_generates_vat_book_line` |
| RF-3 | `account_move.py`, views | `action_regenerate_vat_book_line()` | `test_regenerate_button_updates_lines` |
| RF-4 | `physical_invoice_wizard.py` | `_validate_rif_module_11()` | `test_wizard_validates_rif_module_11` |
| RF-5 | `physical_invoice_wizard.py` | `_create_partner_from_rif()` | `test_wizard_creates_partner_inline` |
| RF-6 | `physical_invoice_wizard.py` | `onchange_partner_vat` (autocompletado) | (integración en test creación) |
| RF-7 | `physical_invoice_wizard.py` | `_get_default_journal()`, `_get_default_account()`, `_get_taxes_for_bases()` | `test_wizard_create_sale_invoice` |
| RF-8 | `account_move.py` | `button_draft()` override | `test_button_draft_deletes_odoo_lines` |
| RF-9 | `vat_book_line.py`, migration | Campos + `post_init_hook` | `test_source_and_audit_fields` |
| RF-10 | `account_move.py` | `_generate_vat_book_line()` loop multi-tax | `test_multi_base_invoice_creates_multiple_lines` |
| RF-11 | `test_export_regression.py` | Export existing code paths | `test_export_xlsx_includes_odoo_lines` |
| RF-12 | `vat_book_line.py`, `import_wizard.py` | `_get_operation_code()` @api.model | `test_get_operation_code_helper` |
| RF-13 | `physical_invoice_wizard.py` | `physical_total` field + onchange warning | `test_wizard_physical_total_warning` |
| RF-14 | `account_move.py`, `regenerate_confirm_wizard.py`, views | `action_regenerate_vat_book_line()` + wizard `l10n.ve.regenerate.confirm.wizard` | `test_regenerate_confirms_manual_edits` |
| RF-15 | `account_tax.py`, `physical_invoice_wizard.py` | `_inherit account.tax` + uso en wizard | `test_account_tax_l10n_ve_type_field` |
| RF-16 | `account_move.py`, `physical_invoice_wizard.py` | `_inherit account.move` + campo en wizard | `test_account_move_control_number_field` |

---

## Preguntas abiertas (requieren confirmación antes de implementar)

1. **Cuenta por defecto para "sin derecho a crédito"**: Usar `property_account_expense_id` del partner + parámetro de compañía `l10n_ve_no_credit_account_id` como fallback (configurable en res.company).

2. **Diarios por defecto compra/venta**: Usar los existentes (`type='purchase'` / `'sale'`). NO crear específicos del módulo.

3. **`vat.book.line` hereda de `mail.thread`**: **SÍ, tracking=True**. La constitution pide trazabilidad visible. Agregar `mail.thread` al `_inherit` si no lo tiene y `tracking=True` en `modified_by`/`modified_at`.

---

**Entrega:** `specs/001-backend-odoo-first/plan.md` — Plan técnico completo con 12 archivos a tocar, 5 funciones puras, 2 algoritmos clave, 3 vistas XML, 5 decisiones justificadas, 15 tests mapeados a RFs, 3 preguntas abiertas pendientes.
