from odoo import fields, models


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
