from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestPhysicalInvoiceWizard(TaxGroupMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({'name': 'Venezuela', 'code': 'VE'})
        self.company.account_fiscal_country_id = self.country

        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Test',
            'vat': 'J-31527189-4',  # RIF válido
        })
        self.company_id = self.company.id

        # Create proper accounts for testing
        self.account_payable = self.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)
        if not self.account_payable:
            self.account_payable = self.env['account.account'].create({
                'name': 'Cuentas por Pagar Test', 'code': '210000', 'account_type': 'liability_payable',
                'company_ids': [(6, 0, [self.company_id])],
            })

        self.account_receivable = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)
        if not self.account_receivable:
            self.account_receivable = self.env['account.account'].create({
                'name': 'Cuentas por Cobrar Test', 'code': '110000', 'account_type': 'asset_receivable',
                'company_ids': [(6, 0, [self.company_id])],
            })

        self.account_expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)
        if not self.account_expense:
            self.account_expense = self.env['account.account'].create({
                'name': 'Gastos Test', 'code': '610000', 'account_type': 'expense',
                'company_ids': [(6, 0, [self.company_id])],
            })

        self.account_income = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)
        if not self.account_income:
            self.account_income = self.env['account.account'].create({
                'name': 'Ingresos Test', 'code': '410000', 'account_type': 'income',
                'company_ids': [(6, 0, [self.company_id])],
            })

        # Set partner payable/receivable accounts
        self.partner.property_account_payable_id = self.account_payable
        self.partner.property_account_receivable_id = self.account_receivable

        self.journal_purchase = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.journal_purchase:
            self.journal_purchase = self.env['account.journal'].create({
                'name': 'Compras Test', 'code': 'PTEST', 'type': 'purchase',
                'company_id': self.company_id,
                'default_account_id': self.account_expense.id,
            })

        self.journal_sale = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.journal_sale:
            self.journal_sale = self.env['account.journal'].create({
                'name': 'Ventas Test', 'code': 'STEST', 'type': 'sale',
                'company_id': self.company_id,
                'default_account_id': self.account_income.id,
            })

        self.tax_group = self._get_or_create_tax_group()

        # Crear impuestos para purchase
        self.tax_general_purchase = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'general'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_general_purchase:
            self.tax_general_purchase = self.env['account.tax'].create({
                'name': 'IVA General 16% (Compra)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'general',
                'type_tax_use': 'purchase',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_reduced_purchase = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 8.0),
            ('l10n_ve_tax_type', '=', 'reduced'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_reduced_purchase:
            self.tax_reduced_purchase = self.env['account.tax'].create({
                'name': 'IVA Reducido 8% (Compra)',
                'amount_type': 'percent',
                'amount': 8.0,
                'l10n_ve_tax_type': 'reduced',
                'type_tax_use': 'purchase',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_additional_purchase = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'additional'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_additional_purchase:
            self.tax_additional_purchase = self.env['account.tax'].create({
                'name': 'IVA Adicional 16% (Compra)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'additional',
                'type_tax_use': 'purchase',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_no_credit_purchase = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'no_credit'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_no_credit_purchase:
            self.tax_no_credit_purchase = self.env['account.tax'].create({
                'name': 'IVA Sin Crédito 16% (Compra)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'no_credit',
                'type_tax_use': 'purchase',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        # Crear impuestos para sale
        self.tax_general_sale = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'general'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_general_sale:
            self.tax_general_sale = self.env['account.tax'].create({
                'name': 'IVA General 16% (Venta)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'general',
                'type_tax_use': 'sale',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_reduced_sale = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 8.0),
            ('l10n_ve_tax_type', '=', 'reduced'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_reduced_sale:
            self.tax_reduced_sale = self.env['account.tax'].create({
                'name': 'IVA Reducido 8% (Venta)',
                'amount_type': 'percent',
                'amount': 8.0,
                'l10n_ve_tax_type': 'reduced',
                'type_tax_use': 'sale',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_additional_sale = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'additional'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_additional_sale:
            self.tax_additional_sale = self.env['account.tax'].create({
                'name': 'IVA Adicional 16% (Venta)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'additional',
                'type_tax_use': 'sale',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_no_credit_sale = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'no_credit'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id),
        ], limit=1)
        if not self.tax_no_credit_sale:
            self.tax_no_credit_sale = self.env['account.tax'].create({
                'name': 'IVA Sin Crédito 16% (Venta)',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'no_credit',
                'type_tax_use': 'sale',
                'company_id': self.company_id,
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
            })

        self.tax_general = self.tax_general_purchase  # Para compatibilidad
        self.account_expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)
        self.account_income = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', [self.company_id]),
        ], limit=1)

    def test_wizard_create_purchase_invoice(self):
        """Crear factura de compra vía wizard y verificar asiento + vat.book.line."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        action = wizard.action_create_and_post()

        # Verificar que se creó el account.move
        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.partner_id, self.partner)
        self.assertEqual(move.amount_total, 1160.0)

        # Verificar vat.book.line
        vbl = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move_id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl), 1)
        self.assertEqual(vbl.source, 'odoo_invoice')
        self.assertEqual(vbl.book_type, 'purchase')
        self.assertEqual(vbl.operation_code, '33')
        self.assertGreater(vbl.base_general, 0)
        self.assertGreater(vbl.vat_general, 0)

    def test_wizard_create_sale_invoice(self):
        """Crear factura de venta vía wizard."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'sale',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'FAC-002',
            'control_number': 'CTRL-002',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.move_type, 'out_invoice')

        vbl = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move_id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl), 1)
        self.assertEqual(vbl.book_type, 'sale')
        self.assertEqual(vbl.operation_code, '42')

    def test_wizard_validates_rif_module_11(self):
        """RIF inválido → ValidationError; RIF válido → OK."""
        # RIF inválido
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-12345678-9',  # DV incorrecto
            'invoice_number': 'FAC-003',
            'control_number': 'CTRL-003',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        with self.assertRaises(ValidationError):
            wizard.action_create_and_post()

        # RIF válido - no debe fallar
        wizard2 = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'FAC-004',
            'control_number': 'CTRL-004',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        # No debe lanzar excepción
        wizard2._validate_rif_module_11('J-31527189-4')

    def test_wizard_creates_partner_inline(self):
        """RIF nuevo → crea partner automáticamente."""
        rif_nuevo = 'V-12345678-5'  # RIF válido (módulo 11 correcto)
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': rif_nuevo,
            'invoice_number': 'FAC-005',
            'control_number': 'CTRL-005',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
            'new_partner_name': 'Nuevo Proveedor Test',
            'new_partner_type': 'company',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)

        # Verificar que se creó el partner
        partner = self.env['res.partner'].search([('vat', '=', rif_nuevo)])
        self.assertTrue(partner)
        self.assertEqual(partner.name, 'Nuevo Proveedor Test')
        self.assertTrue(partner.is_company)
        self.assertEqual(move.partner_id, partner)

    def test_wizard_physical_total_warning(self):
        """physical_total != computed_total → warning, no bloquea."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'FAC-006',
            'control_number': 'CTRL-006',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
            'physical_total': 2000.0,  # No coincide con 1160
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.amount_total, 1160.0)  # Se crea con el calculado
        # physical_total se guarda pero no bloquea
