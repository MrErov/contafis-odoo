from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestVatBookLineSync(TaxGroupMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Test',
            'vat': 'J-12345678-9',
        })
        self.company = self.env.company
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({'name': 'Venezuela', 'code': 'VE'})
        self.company.account_fiscal_country_id = self.country

        # Create proper accounts for testing
        self.account_payable = self.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
            ('company_ids', 'in', [self.company.id]),
        ], limit=1)
        if not self.account_payable:
            self.account_payable = self.env['account.account'].create({
                'name': 'Cuentas por Pagar Test', 'code': '210000', 'account_type': 'liability_payable',
                'company_ids': [(6, 0, [self.company.id])],
            })

        self.account_expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company.id]),
        ], limit=1)
        if not self.account_expense:
            self.account_expense = self.env['account.account'].create({
                'name': 'Gastos Test', 'code': '610000', 'account_type': 'expense',
                'company_ids': [(6, 0, [self.company.id])],
            })

        self.partner.property_account_payable_id = self.account_payable

        self.journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not self.journal:
            self.journal = self.env['account.journal'].create({
                'name': 'Compras Test', 'code': 'PURTEST', 'type': 'purchase',
                'company_id': self.company.id,
                'default_account_id': self.account_expense.id,
            })

        self.tax_group = self._get_or_create_tax_group()

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
                'tax_group_id': self.tax_group.id,
                'country_id': self.country.id,
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

    def test_post_regenerates_safely(self):
        """Verifica que action_post() llama a _generate_vat_book_line() y crea vbl."""
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'l10n_ve_control_number': 'CTRL-002',
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

        # action_post() debe crear la vbl automáticamente
        move.action_post()

        self.assertEqual(move.state, 'posted', "Factura debe estar posteada")
        self.assertGreater(move.amount_total, 0, "Total debe ser > 0")

        vbl = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl), 1, "Debe existir 1 vat.book.line tras post")
        self.assertEqual(vbl.source, 'odoo_invoice')
        self.assertEqual(vbl.book_type, 'purchase')
        self.assertEqual(vbl.operation_code, '33')

    def test_button_draft_deletes_odoo_lines(self):
        """Verifica que button_draft() borra solo source='odoo_invoice'."""
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'l10n_ve_control_number': 'CTRL-003',
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
        move.action_post()

        # Verificar vbl odoo_invoice creada
        vbl_odoo = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl_odoo), 1, "Debe existir 1 vbl odoo_invoice tras post")

        # Crear manualmente vbl con source='manual' vinculada al mismo move
        # Usar operation_code distinto para evitar constraint unique
        vbl_manual = self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': move.name,
            'control_number': 'CTRL-003-MANUAL',
            'operation_code': '30',  # no_credit/not_subject
            'base_not_subject': 500.0,
            'account_move_id': move.id,
            'source': 'manual',
            'company_id': self.company.id,
        })

        # Verificar que ambas existen
        self.assertEqual(
            self.env['l10n.ve.vat.book.line'].search_count([('account_move_id', '=', move.id)]),
            2, "Deben existir 2 vbl (odoo_invoice + manual)"
        )

        # button_draft()
        move.button_draft()

        # Verificar estado
        self.assertEqual(move.state, 'draft', "Factura debe estar en borrador")

        # Verificar que solo odoo_invoice fue borrada
        vbl_odoo_remaining = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl_odoo_remaining), 0, "vbl odoo_invoice debe ser borrada")

        vbl_manual_remaining = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'manual'),
        ])
        self.assertEqual(len(vbl_manual_remaining), 1, "vbl manual debe permanecer")
        self.assertEqual(vbl_manual_remaining.id, vbl_manual.id)

    def test_regenerate_confirm_wizard_flow(self):
        """Verifica flujo del wizard de confirmación para regenerar."""
        # Crear factura y postear
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'l10n_ve_control_number': 'CTRL-004',
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
        move.action_post()

        # Verificar vbl creada
        vbl = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl), 1)

        # Editar la vbl manualmente para marcar is_manually_modified=True
        vbl.write({'base_general': 1500.0})
        self.assertTrue(vbl.is_manually_modified, "vbl debe marcarse como editada manualmente")

        # Llamar action_regenerate_vat_book_line() - debe devolver acción para abrir wizard
        action = move.action_regenerate_vat_book_line()
        self.assertEqual(action['res_model'], 'l10n.ve.regenerate.confirm.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_move_id'], move.id)

        # Crear wizard y confirmar
        wizard = self.env['l10n.ve.regenerate.confirm.wizard'].create({
            'move_id': move.id,
        })
        wizard.action_confirm()

        # Verificar que vbl fue regenerada (is_manually_modified=False)
        # Buscar la nueva vbl (la anterior fue borrada y recreada)
        vbl_new = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
            ('source', '=', 'odoo_invoice'),
        ])
        self.assertEqual(len(vbl_new), 1, "Debe existir 1 vbl tras regeneración")
        self.assertFalse(vbl_new.is_manually_modified, "vbl debe regenerarse y is_manually_modified=False")
        self.assertEqual(vbl_new.base_general, 1000.0, "base_general debe volver al valor original")

        # Caso sin ediciones manuales: action_regenerate_vat_book_line() debe devolver notificación
        move2 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'l10n_ve_control_number': 'CTRL-005',
            'line_ids': [
                (0, 0, {
                    'name': 'Producto Test 2',
                    'account_id': self.account_expense.id,
                    'price_unit': 500.0,
                    'quantity': 1.0,
                    'tax_ids': [(6, 0, [self.tax_general.id])],
                }),
            ],
        })
        move2.action_post()

        action2 = move2.action_regenerate_vat_book_line()
        self.assertEqual(action2['tag'], 'display_notification')
        self.assertEqual(action2['params']['type'], 'success')
