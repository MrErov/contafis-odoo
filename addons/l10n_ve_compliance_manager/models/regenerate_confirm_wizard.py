from odoo import api, fields, models


class RegenerateConfirmWizard(models.TransientModel):
    _name = 'l10n.ve.regenerate.confirm.wizard'
    _description = 'Wizard de confirmación para regenerar libro fiscal'

    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        ondelete='cascade',
    )

    message = fields.Html(
        string='Mensaje',
        compute='_compute_message',
    )

    @api.depends('move_id')
    def _compute_message(self):
        for wizard in self:
            if wizard.move_id:
                manual_count = self.env['l10n.ve.vat.book.line'].search_count([
                    ('account_move_id', '=', wizard.move_id.id),
                    ('source', '=', 'odoo_invoice'),
                    ('is_manually_modified', '=', True),
                ])
                wizard.message = (
                    f"<p>Se detectaron <strong>{manual_count}</strong> línea(s) del libro "
                    f"editadas manualmente para la factura <strong>{wizard.move_id.name}</strong>."
                    f" Regenerar el libro borrará estas ediciones.</p>"
                    f"<p>¿Desea continuar?</p>"
                )
            else:
                wizard.message = ""

    def action_confirm(self):
        """Confirma la regeneración del libro fiscal."""
        self.ensure_one()
        if self.move_id:
            self.move_id._generate_vat_book_line(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': 'Líneas del libro regeneradas correctamente.',
            }
        }
