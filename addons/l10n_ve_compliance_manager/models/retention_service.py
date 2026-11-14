from odoo import fields, models


class L10nVeRetentionService(models.AbstractModel):
    _name = 'l10n.ve.retention.service'
    _description = 'Servicio de cálculo de retenciones venezolanas'

    DEFAULT_RATES = {
        'iva': 75.0,
        'islr': 3.0,
        'igtf': 3.0,
    }

    def get_rate(self, tax_type, company=None):
        """Devuelve la tasa configurada o el fallback por defecto.
        El catálogo l10n.ve.obligation.type es global (sin company_id)."""
        obligation_type = self.env['l10n.ve.obligation.type'].search([
            ('tax_type', '=', tax_type),
            ('base_calculation', '=', 'purchase'),
            ('rate', '>', 0),
        ], limit=1)
        if obligation_type:
            return obligation_type.rate
        return self.DEFAULT_RATES.get(tax_type, 0.0)

    def calculate_amounts(self, move):
        """Devuelve dict con {islr: X, iva: Y, igtf: Z} para una factura in_invoice.
        Retorna dict vacío si move_type != 'in_invoice'."""
        if move.move_type != 'in_invoice':
            return {}
        islr_rate = self.get_rate('islr')
        iva_rate = self.get_rate('iva')
        return {
            'islr': move.amount_untaxed * islr_rate / 100.0 if islr_rate else 0.0,
            'iva': move.amount_tax * iva_rate / 100.0 if iva_rate and move.amount_tax else 0.0,
            'igtf': 0.0,
        }

    def generate_retentions(self, move):
        """Crea registros en l10n.retention para una factura in_invoice.
        Idempotente: no duplica si ya existen retenciones para el mismo move."""
        if move.move_type != 'in_invoice':
            return self.env['l10n.retention']
        self = self.with_company(move.company_id)
        amounts = self.calculate_amounts(move)
        today = fields.Date.today()
        existing = move.retention_ids
        if existing:
            return existing
        vals_list = []
        for tax_type in ('islr', 'iva', 'igtf'):
            amount = amounts.get(tax_type, 0.0)
            if amount:
                vals_list.append({
                    'company_id': move.company_id.id,
                    'partner_id': move.partner_id.id,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'date': move.invoice_date or today,
                    'invoice_id': move.id,
                })
        if vals_list:
            return self.env['l10n.retention'].create(vals_list)
        return self.env['l10n.retention']
