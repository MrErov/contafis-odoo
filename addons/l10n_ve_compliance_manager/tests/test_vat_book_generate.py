from odoo import fields
from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestVatBookGenerate(TaxGroupMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        # Aislar BD: limpiar datos de corridas previas
        self.env['l10n.ve.vat.book.line'].search([]).unlink()
        self.env['l10n.ve.import.line'].search([]).unlink()
        self.env['l10n.ve.import.wizard'].search([]).unlink()
        self.env['l10n.ve.vat.return'].search([]).unlink()

        self.company = self.env.company
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({'name': 'Venezuela', 'code': 'VE'})
        self.company.account_fiscal_country_id = self.country

        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test', 'vat': 'J-12345678-9'})
        self.customer = self.env['res.partner'].create({'name': 'Cliente Test', 'vat': 'V-98765432-1'})

        self.expense_account = self.env['account.account'].create({
            'name': 'Gastos Test', 'code': 'TSTEXP', 'account_type': 'expense',
        })
        self.income_account = self.env['account.account'].create({
            'name': 'Ingresos Test', 'code': 'TSTINC', 'account_type': 'income',
        })
        self.payable_account = self.env['account.account'].create({
            'name': 'CxP Test', 'code': 'TSTPAY', 'account_type': 'liability_payable',
        })
        self.receivable_account = self.env['account.account'].create({
            'name': 'CxC Test', 'code': 'TSTREC', 'account_type': 'asset_receivable',
        })

        self.journal_purchase = self.env['account.journal'].create({
            'name': 'Facturas Proveedor', 'type': 'purchase', 'code': 'TSTPUR',
            'default_account_id': self.expense_account.id,
        })
        self.journal_sale = self.env['account.journal'].create({
            'name': 'Facturas Cliente', 'type': 'sale', 'code': 'TSTSAL',
            'default_account_id': self.income_account.id,
        })

        self.partner.property_account_payable_id = self.payable_account
        self.customer.property_account_receivable_id = self.receivable_account

        self.tax_group = self._get_or_create_tax_group()

        self.tax_iva_16 = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16.0, 'type_tax_use': 'purchase',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })
        self.tax_iva_8 = self.env['account.tax'].create({
            'name': 'IVA 8%', 'amount': 8.0, 'type_tax_use': 'purchase',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })
        self.tax_iva_16_sale = self.env['account.tax'].create({
            'name': 'IVA 16% Venta', 'amount': 16.0, 'type_tax_use': 'sale',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })
        self.tax_iva_8_sale = self.env['account.tax'].create({
            'name': 'IVA 8% Venta', 'amount': 8.0, 'type_tax_use': 'sale',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })

    def _create_in_invoice(self, amount=1000.0, tax_ids=None, date='2026-08-15'):
        vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal_purchase.id,
            'invoice_date': fields.Date.to_date(date),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
                'tax_ids': [(6, 0, tax_ids or [])],
            })],
        }
        return self.env['account.move'].create(vals)

    def _create_out_invoice(self, amount=1000.0, tax_ids=None, date='2026-08-15'):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': fields.Date.to_date(date),
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto Test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.income_account.id,
                'tax_ids': [(6, 0, tax_ids or [])],
            })],
        }
        return self.env['account.move'].create(vals)

    def test_book_generate_from_moves(self):
        """Genera líneas desde facturas del período."""
        # Crear facturas de compra y venta en agosto 2026
        in_inv = self._create_in_invoice(1000.0, [self.tax_iva_16.id], '2026-08-10')
        in_inv.action_post()
        out_inv = self._create_out_invoice(2000.0, [self.tax_iva_16_sale.id], '2026-08-20')
        out_inv.action_post()

        # Factura en otro mes (no debe aparecer)
        self._create_in_invoice(500.0, [self.tax_iva_16.id], '2026-07-10')

        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'both',
        })
        wizard.action_load_moves()

        # Debe detectar 2 facturas
        self.assertEqual(len(wizard.move_ids), 2)

        wizard.action_generate()

        lines = self.env['l10n.ve.vat.book.line'].search([
            ('period_month', '=', '2026-08'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(len(lines), 2)

        purchase_line = lines.filtered(lambda line: line.book_type == 'purchase')
        sale_line = lines.filtered(lambda line: line.book_type == 'sale')

        self.assertEqual(purchase_line.operation_code, '33')
        self.assertEqual(purchase_line.base_general, 1000.0)
        self.assertEqual(purchase_line.vat_general, 160.0)

        self.assertEqual(sale_line.operation_code, '42')
        self.assertEqual(sale_line.base_general, 2000.0)
        self.assertEqual(sale_line.vat_general, 320.0)

    def test_book_no_duplicates(self):
        """Ejecutar wizard 2 veces no duplica líneas."""
        in_inv = self._create_in_invoice(1000.0, [self.tax_iva_16.id])
        in_inv.action_post()

        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_load_moves()
        wizard.action_generate()

        # Segunda vez
        wizard2 = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard2.action_load_moves()
        wizard2.action_generate()

        lines = self.env['l10n.ve.vat.book.line'].search([
            ('period_month', '=', '2026-08'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(len(lines), 1)

    def test_book_operation_codes(self):
        """Verifica códigos de operación correctos por tasa."""
        # IVA 16% compra
        inv1 = self._create_in_invoice(1000.0, [self.tax_iva_16.id])
        inv1.action_post()
        # IVA 8% compra
        inv2 = self._create_in_invoice(1000.0, [self.tax_iva_8.id])
        inv2.action_post()
        # IVA 16% venta
        inv3 = self._create_out_invoice(1000.0, [self.tax_iva_16_sale.id])
        inv3.action_post()
        # IVA 8% venta
        inv4 = self._create_out_invoice(1000.0, [self.tax_iva_8_sale.id])
        inv4.action_post()

        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'both',
        })
        wizard.action_load_moves()
        wizard.action_generate()

        lines = self.env['l10n.ve.vat.book.line'].search([
            ('period_month', '=', '2026-08'),
            ('company_id', '=', self.company.id),
        ])
        codes = lines.mapped('operation_code')
        self.assertIn('33', codes)   # Compra 16%
        self.assertIn('333', codes)  # Compra 8% base
        self.assertIn('42', codes)   # Venta 16%
        self.assertIn('443', codes)  # Venta 8%

    def test_book_retention_link(self):
        """Factura con retención → línea tiene retention_number y vat_retained."""
        inv = self._create_in_invoice(1000.0, [self.tax_iva_16.id])
        inv.action_post()

        # Crear retención manualmente
        self.env['l10n.retention'].create({
            'partner_id': self.partner.id,
            'amount': 120.0,
            'currency_id': self.company.currency_id.id,
            'date': fields.Date.today(),
            'invoice_id': inv.id,
            'state': 'posted',
        })

        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_load_moves()
        wizard.action_generate()

        line = self.env['l10n.ve.vat.book.line'].search([
            ('invoice_number', '=', inv.name),
            ('period_month', '=', '2026-08'),
            ('company_id', '=', self.company.id),
        ])
        self.assertTrue(line.retention_number)
        self.assertEqual(line.vat_retained, 120.0)
        self.assertEqual(line.retention_direction, 'to_vendor')

    def test_book_multi_rate_per_invoice(self):
        """Una factura con líneas IVA 16% y 8% genera 2 líneas de libro."""
        inv = self._create_in_invoice(0, [], '2026-08-10')
        inv.write({
            'invoice_line_ids': [
                (0, 0, {'name': 'Servicio 16%', 'quantity': 1, 'price_unit': 1000.0,
                        'account_id': self.expense_account.id, 'tax_ids': [(6, 0, [self.tax_iva_16.id])]}),
                (0, 0, {'name': 'Servicio 8%', 'quantity': 1, 'price_unit': 500.0,
                        'account_id': self.expense_account.id, 'tax_ids': [(6, 0, [self.tax_iva_8.id])]}),
            ]
        })
        inv.action_post()

        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_load_moves()
        wizard.action_generate()

        lines = self.env['l10n.ve.vat.book.line'].search([
            ('invoice_number', '=', inv.name),
            ('period_month', '=', '2026-08'),
            ('company_id', '=', self.company.id),
        ])
        # Debe crear 2 líneas: una para 16% y otra para 8%
        self.assertEqual(len(lines), 2)
        rates = lines.mapped('operation_code')
        self.assertIn('33', rates)
        self.assertIn('333', rates)
