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

    l10n_ve_invoice_number = fields.Char(
        string='Número de Factura SENIAT',
        copy=False,
        help='Número impreso en la factura física o talonario. '
             'Si se deja vacío, el libro usa el número interno de Odoo.',
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

        # Generar con la misma lógica que el wizard manual (P1-02)
        if not self.invoice_date and not self.date:
            return

        book_line_model = self.env['l10n.ve.vat.book.line']
        for vals in book_line_model._prepare_from_move(self):
            vals.update({
                'account_move_id': self.id,
                'source': 'odoo_invoice',
            })
            book_line_model.create(vals)

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in self.filtered(
            lambda m: m.move_type in ('in_invoice', 'out_invoice')
            and m.company_id.account_fiscal_country_id.code == 'VE'
        ):
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
