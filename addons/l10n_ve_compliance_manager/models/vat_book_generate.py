from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class VatBookGenerate(models.Model):
    _name = 'l10n.ve.vat.book.generate'
    _description = 'Generar Libro de Compras/Ventas desde Facturas'
    _transient_max_count = 0  # No auto-vacuum
    _transient_max_hours = 0

    period_month = fields.Char(
        string='Período (YYYY-MM)',
        required=True,
        default=lambda self: fields.Date.today().strftime('%Y-%m'),
        help='Formato: 2026-08',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    book_type = fields.Selection([
        ('purchase', 'Solo Compras'),
        ('sale', 'Solo Ventas'),
        ('both', 'Compras y Ventas'),
    ], string='Tipo de Libro', default='both', required=True)

    move_ids = fields.Many2many(
        'account.move',
        string='Facturas Detectadas',
        readonly=True,
    )

    line_ids = fields.One2many(
        'l10n.ve.vat.book.line',
        'wizard_id',
        string='Líneas a Crear',
        readonly=True,
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('preview', 'Vista Previa'),
        ('done', 'Generado'),
    ], string='Estado', default='draft')

    def action_load_moves(self):
        """Carga facturas del período y compañía seleccionados."""
        self.ensure_one()

        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
            ('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']),
        ]

        if self.period_month:
            try:
                year, month = map(int, self.period_month.split('-'))
                date_from = fields.Date.to_date(f'{year}-{month:02d}-01')
                if month == 12:
                    date_to = fields.Date.to_date(f'{year + 1}-01-01')
                else:
                    date_to = fields.Date.to_date(f'{year}-{month + 1:02d}-01')
                domain += [
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<', date_to),
                ]
            except Exception:
                raise UserError(_('Formato de período inválido. Use YYYY-MM.'))

        if self.book_type == 'purchase':
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        elif self.book_type == 'sale':
            domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))

        moves = self.env['account.move'].search(domain, order='invoice_date, name')

        self.move_ids = [(6, 0, moves.ids)]
        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.ve.vat.book.generate',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_operation_code_for_rate(self, rate, book_type):
        """Retorna código SENIAT según tasa y tipo de libro."""
        return self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(rate, book_type)

    def _create_book_lines_from_move(self, move):
        """
        Crea líneas de libro para una factura, una por cada tasa de IVA distinta.
        Retorna lista de diccionarios listos para create().
        """
        lines_by_rate = {}

        for line in move.invoice_line_ids:
            for tax in line.tax_ids:
                # Filtrar impuestos de IVA: grupo con nombre que contenga 'IVA' o 'VAT'
                tax_group = tax.tax_group_id
                if not tax_group:
                    continue
                group_name = (tax_group.name or '').upper()
                if 'IVA' not in group_name and 'VAT' not in group_name:
                    continue

                rate = tax.amount
                base = line.price_subtotal
                vat = line.price_total - line.price_subtotal

                if rate not in lines_by_rate:
                    lines_by_rate[rate] = {
                        'base_general': 0.0, 'vat_general': 0.0,
                        'base_reduced': 0.0, 'vat_reduced': 0.0,
                        'base_no_credit': 0.0, 'base_not_subject': 0.0, 'base_not_taxed': 0.0,
                    }

                if rate == 16:
                    lines_by_rate[rate]['base_general'] += base
                    lines_by_rate[rate]['vat_general'] += vat
                elif rate == 8:
                    lines_by_rate[rate]['base_reduced'] += base
                    lines_by_rate[rate]['vat_reduced'] += vat
                elif rate > 16:
                    lines_by_rate[rate]['base_general'] += base
                    lines_by_rate[rate]['vat_general'] += vat
                else:
                    lines_by_rate[rate]['base_not_taxed'] += base

        if not lines_by_rate:
            lines_by_rate[0] = {
                'base_general': 0.0, 'vat_general': 0.0,
                'base_reduced': 0.0, 'vat_reduced': 0.0,
                'base_no_credit': 0.0, 'base_not_subject': 0.0, 'base_not_taxed': move.amount_untaxed,
            }

        if move.move_type in ('out_invoice', 'out_refund'):
            retention_direction = 'by_buyer'
        else:
            retention_direction = 'to_vendor'

        result = []
        for rate, amounts in lines_by_rate.items():
            op_code = self._get_operation_code_for_rate(rate, 'sale' if move.move_type in ('out_invoice', 'out_refund') else 'purchase')
            vals = self.env['l10n.ve.vat.book.line']._prepare_book_line_vals(
                move, rate, amounts, retention_direction, op_code
            )
            vals['wizard_id'] = self.id
            result.append(vals)

        return result

    def action_generate(self):
        """Genera las líneas del libro desde las facturas detectadas."""
        self.ensure_one()

        if not self.move_ids:
            raise UserError(_('No hay facturas cargadas. Ejecute "Cargar Facturas" primero.'))

        BookLine = self.env['l10n.ve.vat.book.line']
        created_count = 0
        updated_count = 0

        for move in self.move_ids:
            line_vals_list = self._create_book_lines_from_move(move)

            for vals in line_vals_list:
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
                    updated_count += 1
                else:
                    BookLine.create(vals)
                    created_count += 1

        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'name': 'Libro de Compras/Ventas Generado',
            'res_model': 'l10n.ve.vat.book.line',
            'view_mode': 'list,form,pivot',
            'domain': [
                ('period_month', '=', self.period_month),
                ('company_id', '=', self.company_id.id),
            ],
            'context': {
                'search_default_group_by_book_type': 1,
            },
        }

    def action_reset(self):
        """Reinicia el wizard."""
        self.ensure_one()
        self.line_ids.unlink()
        self.write({
            'move_ids': [(5, 0, 0)],
            'state': 'draft',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.ve.vat.book.generate',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
