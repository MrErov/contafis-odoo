from odoo import fields, models


class VeRetention(models.Model):
    _name = 'l10n.retention'
    _description = 'Retención'

    company_id = fields.Many2one(
        'res.company', string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )
    name = fields.Char(
        string='Nombre',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence']
            .with_company(self.company_id or self.env.company)
            .next_by_code('l10n.retention'),
    )
    partner_id = fields.Many2one('res.partner', string='Contacto')
    amount = fields.Monetary(string='Monto')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.company.currency_id.id,
    )
    date = fields.Date(string='Fecha')
    invoice_id = fields.Many2one('account.move', string='Factura', ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Publicada'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='draft')

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_post(self):
        self.write({'state': 'posted'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
