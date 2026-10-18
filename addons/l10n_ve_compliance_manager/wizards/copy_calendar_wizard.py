from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class CopyCalendarWizard(models.TransientModel):
    _name = 'l10n.ve.copy.calendar.wizard'
    _description = 'Wizard para copiar el calendario SENIAT a otro año'

    source_year = fields.Integer(string='Año origen', required=True)
    target_year = fields.Integer(string='Año destino', required=True)

    def action_copy(self):
        """Duplica todas las tablas del año origen en el año destino."""
        self.ensure_one()
        table_model = self.env['l10n.ve.seniat.calendar.table']
        source_tables = table_model.search([('year', '=', self.source_year)])
        if not source_tables:
            raise UserError(_(
                'No hay tablas de calendario cargadas para el año %s.'
            ) % self.source_year)
        if table_model.search_count([('year', '=', self.target_year)]):
            raise UserError(_(
                'El año %s ya tiene tablas de calendario. '
                'Elimínelas antes de copiar para evitar duplicados.'
            ) % self.target_year)
        for source in source_tables:
            table_model.create({
                'year': self.target_year,
                'code': source.code,
                'month_offset': source.month_offset,
                'description': source.description,
                'line_ids': [
                    (0, 0, {
                        'month': line.month,
                        'rif_digit': line.rif_digit,
                        'day': line.day,
                    })
                    for line in source.line_ids
                ],
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Calendario SENIAT'),
            'res_model': 'l10n.ve.seniat.calendar.table',
            'view_mode': 'list,form',
            'domain': [('year', '=', self.target_year)],
        }
