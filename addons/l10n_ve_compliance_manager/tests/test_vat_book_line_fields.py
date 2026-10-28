from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVatBookLineFields(TransactionCase):

    def setUp(self):
        super().setUp()
        # Limpiar líneas de libro de IVA preexistentes para evitar conflictos de constraint único
        self.env['l10n.ve.vat.book.line'].search([]).unlink()
        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test'})
        self.company = self.env.company
        self.user = self.env.user

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

    def test_source_and_audit_fields(self):
        """Verifica que vat.book.line tiene campos source, account_move_id, auditoría."""
        model = self.env['l10n.ve.vat.book.line']

        # Verificar campo source
        field_source = model._fields.get('source')
        self.assertIsNotNone(field_source, "Campo source no existe en vat.book.line")
        self.assertEqual(field_source.type, 'selection', "source debe ser Selection")
        selection_values = dict(field_source.selection)
        expected_values = {'odoo_invoice', 'excel_import', 'manual', 'adjustment'}
        self.assertEqual(set(selection_values.keys()), expected_values,
                         f"Valores esperados: {expected_values}, encontrados: {set(selection_values.keys())}")

        # Verificar campo account_move_id
        field_move = model._fields.get('account_move_id')
        self.assertIsNotNone(field_move, "Campo account_move_id no existe en vat.book.line")
        self.assertEqual(field_move.type, 'many2one', "account_move_id debe ser Many2one")
        self.assertEqual(field_move.comodel_name, 'account.move', "account_move_id debe referenciar account.move")

        # Verificar campos de auditoría
        field_modified_by = model._fields.get('modified_by')
        self.assertIsNotNone(field_modified_by, "Campo modified_by no existe")
        self.assertEqual(field_modified_by.type, 'many2one', "modified_by debe ser Many2one")
        self.assertEqual(field_modified_by.comodel_name, 'res.users', "modified_by debe referenciar res.users")

        field_modified_at = model._fields.get('modified_at')
        self.assertIsNotNone(field_modified_at, "Campo modified_at no existe")
        self.assertEqual(field_modified_at.type, 'datetime', "modified_at debe ser Datetime")

        field_is_manual = model._fields.get('is_manually_modified')
        self.assertIsNotNone(field_is_manual, "Campo is_manually_modified no existe")
        self.assertEqual(field_is_manual.type, 'boolean', "is_manually_modified debe ser Boolean")
        self.assertTrue(field_is_manual.compute, "is_manually_modified debe ser computed")
        self.assertTrue(field_is_manual.store, "is_manually_modified debe ser stored")

        # Probar computed field is_manually_modified
        # Caso 1: create_uid == modified_by → False
        line1 = model.create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'company_id': self.company.id,
        })
        self.assertFalse(line1.is_manually_modified, "is_manually_modified debe ser False si no hay edición")

        # Caso 2: write por otro usuario → True (simular modificando modified_by)
        # Usar usuario admin (id=2) que es diferente del usuario actual (id=1)
        other_user = self.env.ref('base.user_admin')
        if other_user and other_user != self.user:
            line1.write({'modified_by': other_user.id})
            line1.invalidate_recordset()
            self.assertTrue(line1.is_manually_modified, "is_manually_modified debe ser True si modified_by != create_uid")

    def test_multiple_lines_per_account_move_allowed(self):
        """Verifica que el modelo permite múltiples vat.book.line con el
        mismo account_move_id (constraint de unicidad permite diferentes
        operation_code).
        """
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-15',
            'journal_id': self.journal.id,
            'name': 'TEST-001',
            'line_ids': [
                (0, 0, {
                    'name': 'Base General',
                    'account_id': self.account_expense.id,
                    'debit': 1000.0,
                    'credit': 0.0,
                }),
            ],
        })

        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': move.name,
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'account_move_id': move.id,
            'source': 'odoo_invoice',
            'company_id': self.company.id,
        })

        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': move.name,
            'control_number': 'CTRL-001',
            'operation_code': '333',
            'base_reduced': 500.0,
            'vat_reduced': 40.0,
            'account_move_id': move.id,
            'source': 'odoo_invoice',
            'company_id': self.company.id,
        })

        lines = self.env['l10n.ve.vat.book.line'].search([('account_move_id', '=', move.id)])
        self.assertEqual(len(lines), 2, "Deben existir 2 líneas para el mismo account_move_id")
        op_codes = sorted(lines.mapped('operation_code'))
        self.assertEqual(op_codes, ['33', '333'], "Códigos de operación distintos")
