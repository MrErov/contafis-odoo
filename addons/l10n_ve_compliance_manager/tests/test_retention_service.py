from odoo import fields
from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestRetentionService(TaxGroupMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        self.service = self.env['l10n.ve.retention.service']

        # Crear país para tests (Venezuela)
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({
                'name': 'Venezuela',
                'code': 'VE',
            })
        self.env.company.account_fiscal_country_id = self.country

        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test'})
        self.expense_account = self.env['account.account'].create({
            'name': 'Gastos Test',
            'code': 'TSTEXP',
            'account_type': 'expense',
        })
        self.payable_account = self.env['account.account'].create({
            'name': 'Cuentas por Pagar Test',
            'code': 'TSTPAY',
            'account_type': 'liability_payable',
        })
        self.journal = self.env['account.journal'].create({
            'name': 'Facturas Proveedor',
            'type': 'purchase',
            'code': 'TSTPUR',
            'default_account_id': self.expense_account.id,
        })
        self.partner.property_account_payable_id = self.payable_account

    def _get_sale_account(self):
        """Obtiene o crea una cuenta de ingresos (income) para ventas."""
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1, order='id')
        if not account:
            account = self.env['account.account'].create({
                'name': 'Test Sale Account',
                'code': '700000',
                'account_type': 'income',
            })
        return account

    def _get_receivable_account(self):
        """Obtiene o crea una cuenta por cobrar (receivable) para partner."""
        account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        if not account:
            account = self.env['account.account'].create({
                'name': 'Test Receivable Account',
                'code': '130000',
                'account_type': 'asset_receivable',
            })
        return account

    def _create_in_invoice(self, amount=1000.0, tax_ids=False):
        vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_date': fields.Date.to_date('2026-01-15'),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        }
        if tax_ids:
            vals['invoice_line_ids'][0][2]['tax_ids'] = [(6, 0, tax_ids)]
        return self.env['account.move'].create(vals)

    def _create_out_invoice(self, amount=1000.0):
        sale_account = self._get_sale_account()
        receivable_account = self._get_receivable_account()

        # Partner para ventas (cliente) con cuenta por cobrar
        customer = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'property_account_receivable_id': receivable_account.id,
        })

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Test Sale Journal',
                'code': 'TSJ',
                'type': 'sale',
                'company_id': self.env.company.id,
                'default_account_id': sale_account.id,
            })
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'partner_id': customer.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'quantity': 1,
                'price_unit': amount,
                'account_id': sale_account.id,
            })],
        })

    def test_get_rate_default(self):
        """Sin configuración en obligation.type → usa DEFAULT_RATES"""
        self.assertEqual(self.service.get_rate('iva'), 75.0)
        self.assertEqual(self.service.get_rate('islr'), 3.0)
        self.assertEqual(self.service.get_rate('igtf'), 3.0)

    def test_get_rate_configured(self):
        """Con obligation.type configurado → devuelve tasa configurada"""
        inst = self.env['l10n.ve.institution'].create({'name': 'SENIAT', 'type': 'seniat'})
        self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Configurado',
            'institution_id': inst.id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'base_calculation': 'purchase',
            'rate': 50.0,
        })
        self.assertEqual(self.service.get_rate('iva'), 50.0)

    def test_calculate_amounts_islr(self):
        """ISLR = 3% del subtotal (amount_untaxed)"""
        move = self._create_in_invoice(amount=1000.0)
        self.assertEqual(move.amount_untaxed, 1000.0)
        amounts = self.service.calculate_amounts(move)
        self.assertEqual(amounts['islr'], 30.0)

    def test_calculate_amounts_iva(self):
        """IVA = 75% del amount_tax (IVA 16% sobre 1000 = 160 → 75% = 120)"""
        tax = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16.0,
            'type_tax_use': 'purchase',
            'amount_type': 'percent',
            'tax_group_id': self._get_or_create_tax_group().id,
            'country_id': self.country.id,
        })
        move = self._create_in_invoice(amount=1000.0, tax_ids=[tax.id])
        self.assertEqual(move.amount_untaxed, 1000.0)
        self.assertEqual(move.amount_tax, 160.0)
        amounts = self.service.calculate_amounts(move)
        self.assertEqual(amounts['iva'], 120.0)

    def test_calculate_amounts_out_invoice(self):
        """En out_invoice retorna dict vacío"""
        move = self._create_out_invoice(amount=1000.0)
        amounts = self.service.calculate_amounts(move)
        self.assertEqual(amounts, {})

    def test_generate_retentions_idempotent(self):
        """Llamar 2 veces no duplica retenciones"""
        move = self._create_in_invoice(amount=1000.0)
        ret1 = self.service.generate_retentions(move)
        ret2 = self.service.generate_retentions(move)
        self.assertEqual(len(ret1), 1)
        self.assertEqual(ret2, ret1)
        self.assertEqual(len(move.retention_ids), 1)

    def test_generate_retentions_not_in_invoice(self):
        """En out_invoice no crea retenciones"""
        move = self._create_out_invoice(amount=1000.0)
        ret = self.service.generate_retentions(move)
        self.assertFalse(ret)
        self.assertFalse(move.retention_ids)

    def test_generate_retentions_iva_and_islr(self):
        """Genera ambas retenciones cuando hay IVA e ISLR"""
        tax = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16.0,
            'type_tax_use': 'purchase',
            'amount_type': 'percent',
            'tax_group_id': self._get_or_create_tax_group().id,
            'country_id': self.country.id,
        })
        move = self._create_in_invoice(amount=1000.0, tax_ids=[tax.id])
        ret = self.service.generate_retentions(move)
        self.assertEqual(len(ret), 2)
        islr_ret = ret.filtered(lambda r: r.amount == 30.0)
        iva_ret = ret.filtered(lambda r: r.amount == 120.0)
        self.assertTrue(islr_ret)
        self.assertTrue(iva_ret)

    def test_generate_retentions_uses_invoice_date(self):
        """Usa invoice_date como fecha de retención"""
        move = self._create_in_invoice(amount=1000.0)
        move.invoice_date = fields.Date.to_date('2026-03-10')
        ret = self.service.generate_retentions(move)
        self.assertEqual(ret.date, fields.Date.to_date('2026-03-10'))
