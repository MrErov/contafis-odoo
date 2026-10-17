from odoo import api, fields, models


class VeBankHoliday(models.Model):
    _name = 'l10n.ve.bank.holiday'
    _description = 'Feriado bancario'
    _order = 'date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Identificación del feriado (ej. "Lunes de Carnaval", "Viernes Santo").',
    )
    date = fields.Date(
        string='Fecha',
        required=True,
        help='Fecha del feriado bancario. El corrimiento a día hábil usa este catálogo.',
    )
    year = fields.Integer(
        string='Año',
        compute='_compute_year',
        store=True,
        help='Año de la fecha (buscable y agrupable).',
    )

    _unique_date = models.Constraint(
        'UNIQUE(date)',
        'Ya existe un feriado bancario en esta fecha.',
    )

    @api.depends('date')
    def _compute_year(self):
        for holiday in self:
            holiday.year = holiday.date.year if holiday.date else False
