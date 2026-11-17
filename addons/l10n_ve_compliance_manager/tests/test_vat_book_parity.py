from odoo import fields
from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestVatBookParity(TaxGroupMixin, TransactionCase):
    """P1-02: la generación automática y el wizard deben producir los mismos valores."""

    def setUp(self):
        super().setUp()
        self.env['l10n.ve.vat.book.line'].search([]).unlink()

        self.company = self.env.company
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({
                'name': 'Venezuela', 'code': 'VE',
            })
        self.company.account_fiscal_country_id = self.country

        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Paridad',
            'vat': 'J-99999999-9',
        })
        self.expense_account = self.env['account.account'].create({
            'name': 'Gastos Paridad',
            'code': 'PAREXP',
            'account_type': 'expense',
        })
        self.payable_account = self.env['account.account'].create({
            'name': 'CxP Paridad',
            'code': 'PARPAY',
            'account_type': 'liability_payable',
        })
        self.partner.property_account_payable_id = self.payable_account

        self.journal = self.env['account.journal'].create({
            'name': 'Compras Paridad',
            'type': 'purchase',
            'code': 'PARPUR',
            'default_account_id': self.expense_account.id,
        })
        self.tax_group = self._get_or_create_tax_group()

    def _create_tax(self, name, amount, amount_type='percent', tax_type='general'):
        return self.env['account.tax'].create({
            'name': name,
            'amount': amount,
            'amount_type': amount_type,
            'l10n_ve_tax_type': tax_type,
            'type_tax_use': 'purchase',
            'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,
            'country_id': self.country.id,
        })

    def _create_invoice(self, tax):
        """Dos facturas idénticas comparten número fiscal y de control."""
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_date': fields.Date.to_date('2026-08-15'),
            'l10n_ve_invoice_number': '001-001-00001234',
            'l10n_ve_control_number': 'CTRL-PARITY-001',
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Paridad',
                'quantity': 1.0,
                'price_unit': 1000.0,
                'account_id': self.expense_account.id,
                'tax_ids': [(6, 0, [tax.id])],
            })],
        })

    def _generate_with_auto(self, move):
        move._generate_vat_book_line()
        return self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])

    def _generate_with_wizard(self, move):
        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
            'move_ids': [(6, 0, [move.id])],
        })
        wizard.action_generate()
        return wizard.line_ids

    def _comparable_values(self, line):
        return {
            'base_general': line.base_general,
            'vat_general': line.vat_general,
            'invoice_number': line.invoice_number,
            'control_number': line.control_number,
        }

    def _assert_parity(self, tax):
        auto_move = self._create_invoice(tax)
        auto_lines = self._generate_with_auto(auto_move)
        self.assertEqual(
            len(auto_lines), 1,
            'La generación automática debe crear exactamente una línea.',
        )
        auto_values = self._comparable_values(auto_lines)
        # Evitar el constraint único: ambas facturas son idénticas.
        auto_lines.unlink()

        wizard_move = self._create_invoice(tax)
        wizard_lines = self._generate_with_wizard(wizard_move)
        self.assertEqual(
            len(wizard_lines), 1,
            'El wizard debe crear exactamente una línea.',
        )
        wizard_values = self._comparable_values(wizard_lines)

        self.assertEqual(auto_values, wizard_values)

    def test_percent_tax_parity(self):
        """IVA porcentual: mismos importes y numeración fiscal en ambos caminos."""
        tax = self._create_tax('IVA Paridad 16%', 16.0)
        self._assert_parity(tax)

    def test_fixed_tax_parity(self):
        """IVA fijo: el importe se calcula con compute_all, no con regla de tres."""
        tax = self._create_tax(
            'IVA Fijo Paridad', 16.0, amount_type='fixed',
        )
        self._assert_parity(tax)
