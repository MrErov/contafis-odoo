from odoo import api, fields, models


class VeSeniatCalendarTable(models.Model):
    _name = 'l10n.ve.seniat.calendar.table'
    _description = 'Tabla del calendario SENIAT por año y literal'
    _order = 'year desc, code'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        help='Identificación de la tabla: año y código (ej. "2026 — a.1 (1ra quincena)").',
    )
    year = fields.Integer(string='Año', required=True)
    code = fields.Selection([
        ('a1', 'a.1 (1ra quincena)'),
        ('a2', 'a.2 (2da quincena)'),
        ('est_islr', 'Estimadas de ISLR'),
        ('ret_islr', 'Retenciones de ISLR'),
    ], string='Código', required=True)
    month_offset = fields.Selection([
        ('0', 'Mismo mes del período'),
        ('1', 'Mes siguiente al período'),
    ], string='Corrimiento de mes', required=True, default='0')
    description = fields.Char(string='Descripción')
    line_ids = fields.One2many(
        'l10n.ve.seniat.calendar', 'table_id', string='Líneas',
    )

    _unique_year_code = models.Constraint(
        'UNIQUE(year, code)',
        'Ya existe una tabla de calendario con este año y código.',
    )

    @api.depends('year', 'code')
    def _compute_name(self):
        code_labels = dict(self._fields['code'].selection)
        for table in self:
            label = code_labels.get(table.code, '')
            if table.year and label:
                table.name = f'{table.year} — {label}'
            else:
                table.name = label


class VeSeniatCalendar(models.Model):
    _name = 'l10n.ve.seniat.calendar'
    _description = 'Día de vencimiento SENIAT por mes y último dígito del RIF'
    _order = 'year desc, month, rif_digit'

    table_id = fields.Many2one(
        'l10n.ve.seniat.calendar.table',
        string='Tabla',
        required=True,
        ondelete='cascade',
    )
    year = fields.Integer(
        string='Año',
        related='table_id.year',
        store=True,
    )
    month = fields.Integer(
        string='Mes',
        required=True,
        help='Mes del período (1 = enero … 12 = diciembre).',
    )
    rif_digit = fields.Integer(
        string='Último dígito del RIF',
        required=True,
        help='Último dígito del RIF del contribuyente (0-9).',
    )
    day = fields.Integer(
        string='Día de vencimiento',
        required=True,
        help='Día del mes en que vence según la tabla oficial.',
    )

    _unique_table_month_digit = models.Constraint(
        'UNIQUE(table_id, month, rif_digit)',
        'Ya existe un día para esta tabla en este mes y dígito de RIF.',
    )
