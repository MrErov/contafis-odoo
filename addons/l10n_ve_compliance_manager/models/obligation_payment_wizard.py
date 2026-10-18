from odoo import _, fields, models
from odoo.exceptions import UserError


class ObligationPaymentWizard(models.TransientModel):
    _name = 'l10n.ve.obligation.payment.wizard'
    _description = 'Wizard para registrar el pago de una obligación'

    obligation_id = fields.Many2one(
        'l10n.ve.obligation',
        string='Obligación',
        required=True,
        ondelete='cascade',
    )
    payment_date = fields.Date(
        string='Fecha de pago',
        required=True,
        default=fields.Date.context_today,
    )
    payment_reference = fields.Char(string='Referencia de pago')
    payment_attachment = fields.Binary(string='Comprobante')

    def action_confirm(self):
        """Registra los datos del pago y marca la obligación como pagada."""
        self.ensure_one()
        obligation = self.obligation_id
        if obligation.state not in ('pending', 'overdue'):
            raise UserError(_(
                'Solo se puede registrar el pago de obligaciones pendientes o vencidas.'
            ))
        values = {'payment_date': self.payment_date}
        if self.payment_reference:
            values['payment_reference'] = self.payment_reference
        if self.payment_attachment:
            values['payment_attachment'] = self.payment_attachment
        obligation.write(values)
        obligation.action_mark_paid()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Se registró el pago de la obligación.'),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
