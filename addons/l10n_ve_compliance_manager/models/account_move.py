from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    emission_type = fields.Selection([
        ('talonario', 'Talonario'),
        ('maquina_fiscal', 'Máquina Fiscal'),
        ('digital', 'Digital'),
    ], string='Tipo de Emisión')

    fiscal_machine_serial = fields.Char(
        string='Serial Máquina Fiscal',
        copy=False,
    )

    fiscal_machine_report_z = fields.Char(
        string='N° Reporte Z',
        copy=False,
    )

    l10n_ve_control_number = fields.Char(
        string='Número de Control SENIAT',
        readonly=True,
        copy=False,
    )

    retention_ids = fields.One2many('l10n.retention', 'invoice_id', string='Retenciones')
    retention_amount = fields.Monetary(
        string='Monto retenido',
        compute='_compute_retention_amount',
        currency_field='currency_id',
    )
    obligation_ids = fields.One2many('l10n.ve.obligation', 'move_id', string='Obligaciones')

    def _generate_vat_book_line(self, force=False):
        """Deriva vat.book.line desde account.move.

        Args:
            force (bool): Si True, omite la verificación de líneas editadas manualmente.

        Returns:
            dict: Acción para abrir wizard si hay líneas editadas manualmente y no force,
                  None si se procesó normalmente.
        """
        self.ensure_one()

        # Verificar líneas editadas manualmente (solo si no force)
        if not force:
            manual_lines = self.env['l10n.ve.vat.book.line'].search([
                ('account_move_id', '=', self.id),
                ('source', '=', 'odoo_invoice'),
                ('is_manually_modified', '=', True)
            ])
            if manual_lines:
                # Retornar acción para abrir wizard de confirmación
                return {
                    'name': 'Confirmar Regeneración',
                    'type': 'ir.actions.act_window',
                    'res_model': 'l10n.ve.regenerate.confirm.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_move_id': self.id},
                }

        # Borrar líneas odoo_invoice existentes
        self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', self.id),
            ('source', '=', 'odoo_invoice')
        ]).unlink()

        # Determinar book_type
        if self.move_type in ('in_invoice', 'in_refund'):
            book_type = 'purchase'
        else:
            book_type = 'sale'

        # Obtener período
        period_month = False
        if self.invoice_date:
            period_month = self.invoice_date.strftime('%Y-%m')
        elif self.date:
            period_month = self.date.strftime('%Y-%m')
        if not period_month:
            return

        # Procesar líneas con impuestos
        for line in self.line_ids:
            if not line.tax_ids:
                continue

            for tax in line.tax_ids:
                rate_type = tax.l10n_ve_tax_type
                if not rate_type:
                    continue

                # Calcular base e IVA
                base = line.price_subtotal
                if base == 0:
                    continue
                vat = tax.amount * base / 100 if tax.amount else 0

                operation_code = self.env['l10n.ve.vat.book.line']._get_operation_code(rate_type, book_type)

                # Calcular retention_direction igual que el wizard
                if self.move_type in ('out_invoice', 'out_refund'):
                    retention_direction = 'by_buyer'
                else:
                    retention_direction = 'to_vendor'

                vals = {
                    'account_move_id': self.id,
                    'source': 'odoo_invoice',
                    'book_type': book_type,
                    'operation_code': operation_code,
                    'partner_id': self.partner_id.id,
                    'invoice_number': self.name or '',
                    'control_number': self.l10n_ve_control_number or self.ref or self.name or '',
                    'period_month': period_month,
                    'company_id': self.company_id.id,
                    'retention_direction': retention_direction,
                }

                # Asignar según rate_type
                if rate_type == 'general':
                    vals['base_general'] = base
                    vals['vat_general'] = vat
                elif rate_type == 'reduced':
                    vals['base_reduced'] = base
                    vals['vat_reduced'] = vat
                elif rate_type == 'import':
                    vals['base_import_16'] = base
                    vals['vat_import_16'] = vat
                elif rate_type == 'no_credit':
                    vals['base_no_credit'] = base
                elif rate_type == 'not_subject':
                    vals['base_not_subject'] = base
                elif rate_type == 'exempt':
                    vals['base_not_taxed'] = base

                # Calcular total_with_vat
                vals['total_with_vat'] = base + vat

                self.env['l10n.ve.vat.book.line'].create(vals)

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in self.filtered(lambda m: m.move_type in ('in_invoice', 'out_invoice')):
            move._generate_vat_book_line()
        return res

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            self.env['l10n.ve.vat.book.line'].search([
                ('account_move_id', '=', move.id),
                ('source', '=', 'odoo_invoice')
            ]).unlink()
        return res

    @api.depends('retention_ids.amount')
    def _compute_retention_amount(self):
        for move in self:
            move.retention_amount = sum(move.retention_ids.mapped('amount'))

    def action_generate_retention(self):
        service = self.env['l10n.ve.retention.service']
        for move in self:
            service.generate_retentions(move)

    def action_regenerate_vat_book_line(self):
        """Regenera líneas del libro fiscal para esta factura."""
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_('Solo facturas posteadas pueden regenerar el libro.'))

        # Verificar si hay líneas editadas manualmente
        manual_lines = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', self.id),
            ('source', '=', 'odoo_invoice'),
            ('is_manually_modified', '=', True)
        ])
        if manual_lines:
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
                'message': _('Líneas del libro regeneradas: %d') % len(self.env['l10n.ve.vat.book.line'].search([
                    ('account_move_id', '=', self.id),
                    ('source', '=', 'odoo_invoice'),
                ])),
            }
        }
