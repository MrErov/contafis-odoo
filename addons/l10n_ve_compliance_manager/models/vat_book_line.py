from odoo import api, fields, models


class VatBookLine(models.Model):
    _name = 'l10n.ve.vat.book.line'
    _description = 'Línea de Libro de Compras/Ventas IVA'
    _order = 'period_month desc, book_type, partner_id, invoice_number'

    book_type = fields.Selection([
        ('purchase', 'Compras'),
        ('sale', 'Ventas'),
    ], string='Tipo de Libro', required=True, index=True)

    period_month = fields.Char(
        string='Período (YYYY-MM)',
        required=True,
        index=True,
        help='Formato: 2026-08',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor / Cliente',
        required=True,
        index=True,
    )

    invoice_number = fields.Char(
        string='Número de Factura',
        required=True,
    )

    control_number = fields.Char(
        string='Número de Control SENIAT',
    )

    operation_code = fields.Char(
        string='Código de Operación SENIAT',
        help='40, 41, 42, 442, 443, 452, 453, 33, 34, 332, 333, 342, 343',
    )

    total_with_vat = fields.Float(
        string='Total con IVA',
        digits='Account',
    )

    base_general = fields.Float(
        string='Base Imponible General (16%)',
        digits='Account',
    )

    vat_general = fields.Float(
        string='IVA General (16%)',
        digits='Account',
    )

    base_import_16 = fields.Float(
        string='Base Importación 16%',
        digits='Account',
    )

    vat_import_16 = fields.Float(
        string='IVA Importación 16%',
        digits='Account',
    )

    base_reduced = fields.Float(
        string='Base Imponible Reducida (8%)',
        digits='Account',
    )

    vat_reduced = fields.Float(
        string='IVA Reducido (8%)',
        digits='Account',
    )

    base_no_credit = fields.Float(
        string='Base Sin Crédito Fiscal',
        digits='Account',
    )

    base_not_subject = fields.Float(
        string='Base No Sujeta',
        digits='Account',
    )

    base_not_taxed = fields.Float(
        string='Base No Gravada',
        digits='Account',
    )

    retention_number = fields.Char(
        string='Número de Comprobante de Retención',
    )

    vat_retained = fields.Float(
        string='IVA Retenido',
        digits='Account',
    )

    retention_direction = fields.Selection([
        ('by_buyer', 'Retenido por comprador'),
        ('to_vendor', 'Retenido a vendedor'),
        ('to_third', 'Retenido a terceros'),
    ], string='Dirección Retención', default='to_vendor')

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    wizard_id = fields.Many2one(
        'l10n.ve.vat.book.generate',
        string='Wizard',
        ondelete='cascade',
    )

    source = fields.Selection([
        ('odoo_invoice', 'Factura Odoo'),
        ('excel_import', 'Importación Excel'),
        ('manual', 'Manual'),
        ('adjustment', 'Ajuste'),
    ], string='Origen', default='manual', required=True, index=True)

    account_move_id = fields.Many2one(
        'account.move',
        string='Asiento Contable',
        ondelete='set null',
        readonly=True,
        index=True,
    )

    modified_by = fields.Many2one(
        'res.users',
        string='Modificado por',
    )

    modified_at = fields.Datetime(
        string='Modificado en',
        readonly=True,
    )

    is_manually_modified = fields.Boolean(
        string='Editado Manual',
        compute='_compute_is_manually_modified',
        store=True,
        readonly=True,
    )

    @api.depends('modified_by', 'create_uid')
    def _compute_is_manually_modified(self):
        for record in self:
            record.is_manually_modified = bool(record.modified_by) and record.modified_by != record.create_uid

    @api.model
    def _get_operation_code(self, rate_type: str, book_type: str) -> str:
        """
        Retorna código SENIAT según rate_type y book_type.
        rate_type: 'import', 'general', 'reduced', 'no_credit', 'not_subject', 'non_contrib'
        book_type: 'purchase', 'sale'
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

    _unique_line = models.Constraint(
        'UNIQUE(partner_id, invoice_number, control_number, period_month, company_id, operation_code, retention_direction)',
        'Ya existe una línea para esta factura en el período con ese código de operación y dirección de retención.',
    )

    @api.model
    def _get_operation_code_for_rate(self, rate, book_type):
        """Retorna código SENIAT según tasa y tipo de libro."""
        if book_type == 'sale':
            if rate == 16:
                return '42'
            elif rate == 8:
                return '443'
            elif rate > 16:
                return '442'
            else:
                return '40'
        else:
            if rate == 16:
                return '33'
            elif rate == 8:
                return '333'
            elif rate > 16:
                return '332'
            else:
                return '30'

    @api.model
    def _prepare_book_line_vals(self, move, rate, amounts, retention_direction, op_code):
        """Prepara valores para crear una línea de libro desde una factura y una tasa."""
        if move.move_type in ('out_invoice', 'out_refund'):
            book_type = 'sale'
        else:
            book_type = 'purchase'

        sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1

        vals = {
            'book_type': book_type,
            'period_month': move.invoice_date.strftime('%Y-%m') if move.invoice_date else fields.Date.today().strftime('%Y-%m'),
            'partner_id': move.partner_id.id,
            'invoice_number': move.name or '',
            'control_number': move.ref or move.name or '',
            'operation_code': op_code,
            'total_with_vat': sign * (amounts['base_general'] + amounts['vat_general'] + amounts['base_reduced'] + amounts['vat_reduced'] + amounts['base_not_taxed']),
            'base_general': sign * amounts['base_general'],
            'vat_general': sign * amounts['vat_general'],
            'base_reduced': sign * amounts['base_reduced'],
            'vat_reduced': sign * amounts['vat_reduced'],
            'base_no_credit': sign * amounts['base_no_credit'],
            'base_not_subject': sign * amounts['base_not_subject'],
            'base_not_taxed': sign * amounts['base_not_taxed'],
            'retention_number': False,
            'vat_retained': 0.0,
            'retention_direction': retention_direction,
            'company_id': move.company_id.id,
        }

        if move.retention_ids:
            retentions = move.retention_ids.filtered(lambda r: r.state == 'posted')
            if retentions:
                vals['retention_number'] = ', '.join(retentions.mapped('name'))
                vals['vat_retained'] = sign * sum(retentions.mapped('amount'))

        return vals

    @api.model
    def create_from_move(self, move):
        """Crea líneas de libro desde una factura (método de conveniencia para tests y uso directo)."""
        wizard_dummy = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': move.invoice_date.strftime('%Y-%m') if move.invoice_date else fields.Date.today().strftime('%Y-%m'),
            'company_id': move.company_id.id,
            'book_type': 'both',
        })
        line_vals_list = wizard_dummy._create_book_lines_from_move(move)
        for vals in line_vals_list:
            vals['wizard_id'] = wizard_dummy.id
            self.create(vals)
        return True

    def action_open_export_wizard(self):
        """Abre el wizard de exportación con el período de las líneas seleccionadas."""
        self.ensure_one()
        # Si hay múltiples líneas seleccionadas, usar el período de la primera
        period_month = self.period_month
        company_id = self.company_id.id
        book_type = self.book_type

        return {
            'type': 'ir.actions.act_window',
            'name': 'Exportar Libro IVA a Excel',
            'res_model': 'l10n.ve.vat.book.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_month': period_month,
                'default_company_id': company_id,
                'default_book_type': book_type,
            },
        }
