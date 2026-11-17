from odoo import api, fields, models

#: Campos del libro que alimenta cada tipo de tasa SENIAT.
#: El segundo elemento es el campo de IVA (None si la columna no lleva IVA).
RATE_TYPE_FIELDS = {
    'general': ('base_general', 'vat_general'),
    'additional': ('base_general', 'vat_general'),
    'non_contrib': ('base_general', 'vat_general'),
    'reduced': ('base_reduced', 'vat_reduced'),
    'import': ('base_import_16', 'vat_import_16'),
    'no_credit': ('base_no_credit', None),
    'not_subject': ('base_not_subject', None),
    'exempt': ('base_not_taxed', None),
    'not_taxed': ('base_not_taxed', None),
}

#: Importes acumulados por línea del libro.
EMPTY_BOOK_AMOUNTS = {
    'base_general': 0.0,
    'vat_general': 0.0,
    'base_import_16': 0.0,
    'vat_import_16': 0.0,
    'base_reduced': 0.0,
    'vat_reduced': 0.0,
    'base_no_credit': 0.0,
    'base_not_subject': 0.0,
    'base_not_taxed': 0.0,
}


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

    invoice_date = fields.Date(
        string='Fecha de Factura',
        index=True,
        help='Fecha de emisión de la factura. Se conserva para el export y la reimportación.',
    )

    invoice_type = fields.Char(
        string='Tipo de Documento SENIAT',
        help='01 Factura, 03 Nota de Crédito. Se completa desde la factura o el Excel.',
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

    anticipo_import = fields.Float(
        string='Anticipo IVA Importación',
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
            # True si ha sido modificada (modified_by tiene valor), independientemente de quién la creó
            record.is_manually_modified = bool(record.modified_by)

    def write(self, vals):
        """Actualiza campos de auditoría al editar manualmente."""
        if 'modified_by' not in vals:
            vals['modified_by'] = self.env.user.id
        vals['modified_at'] = fields.Datetime.now()
        return super().write(vals)

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
    def _is_vat_tax(self, tax):
        """True si el impuesto es de IVA y debe entrar al libro fiscal."""
        if tax.l10n_ve_tax_type:
            return True
        group_name = (tax.tax_group_id.name or '').upper()
        return 'IVA' in group_name or 'VAT' in group_name

    @api.model
    def _get_tax_rate_type(self, tax):
        """Clasifica un impuesto en la columna SENIAT del libro.

        Los impuestos con ``l10n_ve_tax_type`` usan esa clasificación. Sin
        metadatos SENIAT (datos de prueba o impuestos genéricos) se infiere
        desde la tasa, igual que hacía el wizard.
        """
        if tax.l10n_ve_tax_type:
            return tax.l10n_ve_tax_type
        if tax.amount == 8:
            return 'reduced'
        if tax.amount >= 16:
            return 'general'
        return 'not_taxed'

    @api.model
    def _get_tax_operation_code(self, tax, book_type):
        """Código de operación SENIAT para un impuesto."""
        if tax.l10n_ve_tax_type in (
            'general', 'reduced', 'no_credit', 'not_subject', 'exempt',
            'non_contrib', 'import',
        ):
            return self._get_operation_code(tax.l10n_ve_tax_type, book_type)
        return self._get_operation_code_for_rate(tax.amount, book_type)

    @api.model
    def _prepare_from_move(self, move):
        """Prepara las líneas del libro IVA de una factura.

        Centraliza el cálculo usado por la generación automática
        (``account.move._generate_vat_book_line``) y por el wizard. El IVA se
        obtiene con ``tax.compute_all`` para respetar impuestos fijos,
        redondeos e impuestos incluidos en el precio, y la numeración fiscal
        sale de los campos SENIAT con fallback a los campos internos.

        Returns:
            list[dict]: valores listos para ``create()``, uno por tasa/código.
        """
        book_type = 'sale' if move.move_type in (
            'out_invoice', 'out_refund',
        ) else 'purchase'
        retention_direction = 'by_buyer' if book_type == 'sale' else 'to_vendor'
        is_refund = move.move_type in ('in_refund', 'out_refund')

        lines_by_taxes = {}
        for line in move.invoice_line_ids:
            taxes = line.tax_ids.filtered(self._is_vat_tax)
            if not taxes:
                continue

            computed = taxes.compute_all(
                line.price_unit,
                currency=line.currency_id or move.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.partner_id or move.partner_id,
                is_refund=is_refund,
            )
            for tax_data in computed.get('taxes', []):
                tax = self.env['account.tax'].browse(tax_data['id'])
                if tax not in taxes:
                    continue
                rate_type = self._get_tax_rate_type(tax)
                op_code = self._get_tax_operation_code(tax, book_type)
                amounts = lines_by_taxes.setdefault(
                    (rate_type, op_code), dict(EMPTY_BOOK_AMOUNTS),
                )
                base_field, vat_field = RATE_TYPE_FIELDS[rate_type]
                amounts[base_field] += tax_data['base']
                if vat_field:
                    amounts[vat_field] += tax_data['amount']

        if not lines_by_taxes:
            fallback = dict(EMPTY_BOOK_AMOUNTS)
            fallback['base_not_taxed'] = move.amount_untaxed
            lines_by_taxes[(
                'not_taxed', self._get_operation_code_for_rate(0, book_type),
            )] = fallback

        return [
            self._prepare_book_line_vals(
                move, 0.0, amounts, retention_direction, op_code,
            )
            for (_rate_type, op_code), amounts in lines_by_taxes.items()
        ]

    @api.model
    def _prepare_book_line_vals(self, move, rate, amounts, retention_direction, op_code):
        """Prepara valores para crear una línea de libro desde una factura y una tasa."""
        if move.move_type in ('out_invoice', 'out_refund'):
            book_type = 'sale'
        else:
            book_type = 'purchase'

        sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1
        period_date = move.invoice_date or move.date
        period_month = (
            period_date.strftime('%Y-%m')
            if period_date else fields.Date.today().strftime('%Y-%m')
        )
        total_with_vat = (
            amounts.get('base_general', 0.0) + amounts.get('vat_general', 0.0)
            + amounts.get('base_reduced', 0.0) + amounts.get('vat_reduced', 0.0)
            + amounts.get('base_no_credit', 0.0) + amounts.get('base_not_subject', 0.0)
            + amounts.get('base_not_taxed', 0.0)
            + amounts.get('base_import_16', 0.0) + amounts.get('vat_import_16', 0.0)
        )

        vals = {
            'book_type': book_type,
            'period_month': period_month,
            'partner_id': move.partner_id.id,
            'invoice_number': move.l10n_ve_invoice_number or move.name or '',
            'invoice_date': move.invoice_date or False,
            'invoice_type': '03' if move.move_type in ('in_refund', 'out_refund') else '01',
            'control_number': move.l10n_ve_control_number or move.ref or move.name or '',
            'operation_code': op_code,
            'total_with_vat': sign * total_with_vat,
            'base_general': sign * amounts.get('base_general', 0.0),
            'vat_general': sign * amounts.get('vat_general', 0.0),
            'base_import_16': sign * amounts.get('base_import_16', 0.0),
            'vat_import_16': sign * amounts.get('vat_import_16', 0.0),
            'base_reduced': sign * amounts.get('base_reduced', 0.0),
            'vat_reduced': sign * amounts.get('vat_reduced', 0.0),
            'base_no_credit': sign * amounts.get('base_no_credit', 0.0),
            'base_not_subject': sign * amounts.get('base_not_subject', 0.0),
            'base_not_taxed': sign * amounts.get('base_not_taxed', 0.0),
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
        move = move.with_company(move.company_id)
        wizard_dummy = self.env['l10n.ve.vat.book.generate'].with_company(move.company_id).create({
            'period_month': move.invoice_date.strftime('%Y-%m') if move.invoice_date else fields.Date.today().strftime('%Y-%m'),
            'company_id': move.company_id.id,
            'book_type': 'both',
        })
        line_vals_list = wizard_dummy._create_book_lines_from_move(move)
        BookLine = self.with_company(move.company_id)
        for vals in line_vals_list:
            vals['wizard_id'] = wizard_dummy.id
            existing = BookLine.search([
                ('partner_id', '=', vals['partner_id']),
                ('invoice_number', '=', vals['invoice_number']),
                ('control_number', '=', vals['control_number']),
                ('period_month', '=', vals['period_month']),
                ('company_id', '=', vals['company_id']),
                ('operation_code', '=', vals['operation_code']),
                ('retention_direction', '=', vals['retention_direction']),
            ], limit=1)
            if existing:
                existing.write(vals)
            else:
                BookLine.create(vals)
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
