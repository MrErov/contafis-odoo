
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PhysicalInvoiceWizard(models.TransientModel):
    _name = 'l10n.ve.physical.invoice.wizard'
    _description = 'Wizard para carga rápida de factura física'

    # Identificación
    type = fields.Selection([
        ('purchase', 'Compra'),
        ('sale', 'Venta'),
    ], string='Tipo de Operación', required=True, default='purchase')

    partner_vat = fields.Char(string='RIF', required=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor/Cliente', readonly=True)
    partner_name = fields.Char(related='partner_id.name', string='Razón Social', readonly=True)

    # Nuevo partner (se muestra si no existe)
    new_partner_name = fields.Char(string='Razón Social (nuevo)')
    new_partner_type = fields.Selection([
        ('company', 'Empresa'),
        ('person', 'Persona'),
    ], string='Tipo de Proveedor/Cliente', default='company')
    new_partner_street = fields.Char(string='Dirección')
    new_partner_email = fields.Char(string='Email')
    new_partner_phone = fields.Char(string='Teléfono')

    invoice_number = fields.Char(string='Número de Factura', required=True)
    control_number = fields.Char(string='Número de Control', required=True)
    invoice_date = fields.Date(string='Fecha de Emisión', required=True, default=fields.Date.today)
    invoice_date_due = fields.Date(string='Fecha de Vencimiento')

    # Tipo de Emisión
    emission_type = fields.Selection([
        ('talonario', 'Talonario'),
        ('maquina_fiscal', 'Máquina Fiscal'),
        ('digital', 'Digital'),
    ], string='Tipo de Emisión', default='talonario', required=True)

    fiscal_machine_serial = fields.Char(string='Serial Máquina Fiscal')
    fiscal_machine_report_z = fields.Char(string='N° Reporte Z')

    # Bases e IVA
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    base_general = fields.Monetary(string='Base General 16%', default=0.0)
    vat_general = fields.Monetary(string='IVA General 16%', compute='_compute_vat_amounts', store=True, readonly=True)
    base_reduced = fields.Monetary(string='Base Reducida 8%', default=0.0)
    vat_reduced = fields.Monetary(string='IVA Reducido 8%', compute='_compute_vat_amounts', store=True, readonly=True)
    base_additional = fields.Monetary(string='Base Adicional >16%', default=0.0)
    vat_additional = fields.Monetary(string='IVA Adicional >16%', compute='_compute_vat_amounts', store=True, readonly=True)
    base_not_subject = fields.Monetary(string='Base No Sujeta', default=0.0)
    base_not_taxed = fields.Monetary(string='Base No Gravada', default=0.0)
    base_no_credit = fields.Monetary(string='Base Sin Crédito', default=0.0)
    vat_no_credit = fields.Monetary(string='IVA Sin Crédito', compute='_compute_vat_amounts', store=True, readonly=True)

    # Retención
    retention_number = fields.Char(string='Número Comprobante Retención')
    retention_vat = fields.Monetary(string='IVA Retenido')
    retention_direction = fields.Selection([
        ('by_buyer', 'Retenido por comprador'),
        ('to_vendor', 'Retenido a vendedor'),
        ('to_third', 'Retenido a terceros'),
    ], string='Dirección Retención', default='to_vendor')

    # Otros
    concept = fields.Char(string='Concepto')
    physical_total = fields.Monetary(string='Total según factura física (Bs)', help='Total según factura física (solo informativo)')
    computed_total = fields.Monetary(string='Total Calculado', compute='_compute_computed_total', readonly=True)

    @api.depends('base_general', 'base_reduced', 'base_additional', 'base_no_credit')
    def _compute_vat_amounts(self):
        for rec in self:
            rec.vat_general = rec.base_general * 0.16
            rec.vat_reduced = rec.base_reduced * 0.08
            rec.vat_additional = rec.base_additional * 0.16
            rec.vat_no_credit = rec.base_no_credit * 0.16

    @api.depends('base_general', 'base_reduced', 'base_additional', 'base_not_subject', 'base_not_taxed',
                 'base_no_credit', 'vat_general', 'vat_reduced', 'vat_additional', 'vat_no_credit')
    def _compute_computed_total(self):
        for rec in self:
            rec.computed_total = (rec.base_general + rec.base_reduced + rec.base_additional +
                                  rec.base_not_subject + rec.base_not_taxed + rec.base_no_credit +
                                  rec.vat_general + rec.vat_reduced + rec.vat_additional + rec.vat_no_credit)

    @api.onchange('partner_vat')
    def _onchange_partner_vat(self):
        """Valida RIF y busca/crea partner."""
        if not self.partner_vat:
            self.partner_id = False
            return

        # Validar RIF módulo 11
        if not self._validate_rif_module_11(self.partner_vat):
            raise ValidationError(_('RIF inválido (dígito de control incorrecto)'))

        # Buscar partner por RIF (case-insensitive, sin guiones)
        rif_clean = self._clean_rif(self.partner_vat)
        partner = self.env['res.partner'].search([
            '|', ('vat', '=', self.partner_vat), ('vat', '=', rif_clean)
        ], limit=1)

        if partner:
            self.partner_id = partner.id
            self.partner_name = partner.name
        else:
            self.partner_id = False
            # Se expande la sección "Nuevo partner" en la vista

    @api.model
    def _clean_rif(self, rif):
        """Limpia RIF para búsqueda."""
        if not rif:
            return ''
        return str(rif).strip().upper().replace('-', '').replace('.', '').replace(' ', '')

    def _get_default_journal(self, type_move):
        """Obtiene diario por defecto según tipo."""
        journal_type = 'purchase' if type_move == 'purchase' else 'sale'
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        return journal

    def _get_default_account(self, type_move):
        """Obtiene cuenta por defecto según tipo."""
        if type_move == 'purchase':
            return self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_ids', 'in', [self.env.company.id]),
            ], limit=1)
        else:
            return self.env['account.account'].search([
                ('account_type', '=', 'income'),
                ('company_ids', 'in', [self.env.company.id]),
            ], limit=1)

    def _get_taxes_for_bases(self):
        """Busca taxes por l10n_ve_tax_type según bases > 0."""
        taxes = {}
        if self.base_general > 0:
            tax = self.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', 'general'),
                ('type_tax_use', '=', 'purchase' if self.type == 'purchase' else 'sale'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if tax:
                taxes['general'] = tax.id
        if self.base_reduced > 0:
            tax = self.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', 'reduced'),
                ('type_tax_use', '=', 'purchase' if self.type == 'purchase' else 'sale'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if tax:
                taxes['reduced'] = tax.id
        if self.base_additional > 0:
            tax = self.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', 'additional'),
                ('type_tax_use', '=', 'purchase' if self.type == 'purchase' else 'sale'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if tax:
                taxes['additional'] = tax.id
        if self.base_no_credit > 0:
            tax = self.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', 'no_credit'),
                ('type_tax_use', '=', 'purchase' if self.type == 'purchase' else 'sale'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if tax:
                taxes['no_credit'] = tax.id
        return taxes

    def _build_move_lines_from_bases(self):
        """Construye líneas de account.move desde bases del wizard.

        En Odoo, las líneas de factura usan price_unit = base (sin IVA)
        y tax_ids para que Odoo calcule automáticamente el IVA y cree
        las líneas de impuesto. El total de la línea (price_total) = base + IVA.
        """
        self.ensure_one()
        taxes = self._get_taxes_for_bases()
        account = self._get_default_account(self.type)

        lines = []

        # Helper para agregar línea base + tax
        def add_base_line(base_amount, tax_key):
            if base_amount <= 0 or tax_key not in taxes:
                return
            lines.append((0, 0, {
                'name': self.concept or 'Factura física',
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': base_amount,  # Base sin IVA
                'tax_ids': [(6, 0, [taxes[tax_key]])],
            }))

        # Línea por cada base > 0 con su tax
        if self.base_general > 0 and 'general' in taxes:
            lines.append((0, 0, {
                'name': self.concept or 'Factura física',
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': self.base_general,
                'tax_ids': [(6, 0, [taxes['general']])],
            }))

        if self.base_reduced > 0 and 'reduced' in taxes:
            lines.append((0, 0, {
                'name': self.concept or 'Factura física',
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': self.base_reduced,
                'tax_ids': [(6, 0, [taxes['reduced']])],
            }))

        if self.base_additional > 0 and 'additional' in taxes:
            lines.append((0, 0, {
                'name': self.concept or 'Factura física',
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': self.base_additional,
                'tax_ids': [(6, 0, [taxes['additional']])],
            }))

        if self.base_no_credit > 0 and 'no_credit' in taxes:
            lines.append((0, 0, {
                'name': self.concept or 'Factura física',
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': self.base_no_credit,
                'tax_ids': [(6, 0, [taxes['no_credit']])],
            }))

        # Bases sin IVA (sin tax_ids)
        for base_field in ['base_not_subject', 'base_not_taxed']:
            base_val = getattr(self, base_field)
            if base_val > 0:
                lines.append((0, 0, {
                    'name': self.concept or 'Factura física',
                    'account_id': account.id,
                    'quantity': 1.0,
                    'price_unit': base_val,
                    'tax_ids': [(5, 0, 0)],
                }))

        # Línea de CxP/CxC - Odoo la calcula automáticamente al postear
        # basándose en partner_id y move_type
        # No necesitamos añadirla manualmente, Odoo la genera al postear
        # basándose en partner_id y move_type

        return lines

    def _validate_rif_module_11(self, rif):
        """Reusa validador RIF módulo 11 del import_wizard."""
        return self.env['l10n.ve.import.wizard']._validate_rif(rif)

    def action_create_and_post(self):
        """Valida, crea account.move, postea, retorna acción para abrir factura."""
        self.ensure_one()

        # Validaciones
        if all(b == 0 for b in [self.base_general, self.base_reduced, self.base_additional,
                                self.base_not_subject, self.base_not_taxed, self.base_no_credit]):
            raise ValidationError(_('Al menos una base debe ser mayor a 0'))

        if any(b < 0 for b in [self.base_general, self.base_reduced, self.base_additional,
                                self.base_not_subject, self.base_not_taxed, self.base_no_credit]):
            raise ValidationError(_('Las bases no pueden ser negativas'))

        # Validar RIF
        if not self._validate_rif_module_11(self.partner_vat):
            raise ValidationError(_('RIF inválido (dígito de control incorrecto)'))

        # Buscar o crear partner
        rif_clean = self._clean_rif(self.partner_vat)
        partner = self.env['res.partner'].search([
            '|', ('vat', '=', self.partner_vat), ('vat', '=', rif_clean)
        ], limit=1)

        if not partner:
            if not self.new_partner_name:
                raise ValidationError(_('Debe ingresar la razón social para crear el partner'))
            partner = self.env['res.partner'].create({
                'name': self.new_partner_name,
                'vat': self.partner_vat,
                'is_company': self.new_partner_type == 'company',
                'street': self.new_partner_street,
                'email': self.new_partner_email,
                'phone': self.new_partner_phone,
            })

        # Sincronizar partner_id
        self.partner_id = partner.id

        # Obtener diario y cuenta
        journal = self._get_default_journal(self.type)
        account = self._get_default_account(self.type)

        if not journal:
            raise ValidationError(_('No hay diario configurado para %s') % ('compras' if self.type == 'purchase' else 'ventas'))
        if not account:
            raise ValidationError(_('No hay cuenta configurada para %s') % ('gastos' if self.type == 'purchase' else 'ingresos'))

        # Construir líneas
        move_lines = self._build_move_lines_from_bases()

        # Crear factura
        move_type = 'in_invoice' if self.type == 'purchase' else 'out_invoice'
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': self.invoice_date,
            'invoice_date_due': self.invoice_date_due,
            'ref': self.control_number,
            'narration': self.concept,
            'line_ids': move_lines,
            'emission_type': self.emission_type,
            'fiscal_machine_serial': self.fiscal_machine_serial,
            'fiscal_machine_report_z': self.fiscal_machine_report_z,
        })

        # Postear
        move.action_post()

        # Retornar acción para abrir la factura
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }
