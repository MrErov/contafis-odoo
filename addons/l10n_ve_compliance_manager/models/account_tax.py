from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_ve_tax_type = fields.Selection([
        ('general', 'General 16%'),
        ('reduced', 'Reducida 8%'),
        ('additional', 'Adicional >16%'),
        ('no_credit', 'Sin Crédito Fiscal'),
        ('exempt', 'Exento'),
        ('not_subject', 'No Sujeto'),
        ('import', 'Importación'),
        ('non_contrib', 'No Contribuyente'),
    ], string='Tipo Tasa SENIAT', help='Clasificación de la tasa para libro fiscal SENIAT (planilla 99030)')
