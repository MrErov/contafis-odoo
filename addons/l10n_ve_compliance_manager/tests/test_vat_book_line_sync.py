from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVatBookLineSync(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Test',
            'vat': 'J-12345678-9',
        })
        self.company = self.env.company
        self.journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.account_expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company.id]),
        ], limit=1)
        self.tax_general = self.env['account.tax'].search([
            ('amount_type', '=', 'percent'),
            ('amount', '=', 16.0),
            ('l10n_ve_tax_type', '=', 'general'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not self.tax_general:
            self.tax_general = self.env['account.tax'].create({
                'name': 'IVA General 16%',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': 'general',
                'type_tax_use': 'purchase',
                'company_id': self.company.id,
            })

    def test_account_move_control_number_field(self):
        """Verifica que account.move tiene campo l10n_ve_control_number (Char, copy=False)."""
        model = self.env['account.move']
        field = model._fields.get('l10n_ve_control_number')
        self.assertIsNotNone(field, "Campo l10n_ve_control_number no existe en account.move")
        self.assertEqual(field.type, 'char', "l10n_ve_control_number debe ser Char")
        self.assertFalse(field.copy, "l10n_ve_control_number debe tener copy=False")

    def test_post_invoice_generates_vat_book_line(self):
        """Verifica que _generate_vat_book_line() crea vat.book.line con source='odoo_invoice'."""
        # Crear factura de compra con tax general
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'l10n_ve_control_number': 'CTRL-001',
            'line_ids': [
                (0, 0, {
                    'name': 'Producto Test',
                    'account_id': self.account_expense.id,
                    'price_unit': 1000.0,
                    'quantity': 1.0,
                    'tax_ids': [(6, 0, [self.tax_general.id])],
                }),
            ],
        })

        # NO llamar action_post() - solo probar el método directamente
        move._generate_vat_book_line()

        # Verificar que se creó la línea
        vbl = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl), 1, "Debe existir 1 vat.book.line")
        self.assertEqual(vbl.account_move_id, move)
        self.assertEqual(vbl.source, 'odoo_invoice')
        self.assertEqual(vbl.book_type, 'purchase')
        self.assertEqual(vbl.operation_code, '33')
        self.assertGreater(vbl.base_general, 0)
        self.assertGreater(vbl.vat_general, 0)
        self.assertEqual(vbl.partner_id, self.partner)
        self.assertEqual(vbl.invoice_number, move.name or '')
        self.assertEqual(vbl.control_number, 'CTRL-001')
        self.assertEqual(vbl.period_month, '2026-08')
        self.assertEqual(vbl.company_id, self.company)

        # Verificar idempotencia: llamar 2 veces no duplica
        move._generate_vat_book_line()
        vbl2 = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl2), 1, "Segunda llamada no debe duplicar la línea")
