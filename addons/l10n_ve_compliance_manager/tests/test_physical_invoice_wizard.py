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
        self.assertEqual(partner.company_type, 'company')
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

    # --- T4: Notas de crédito y débito (RF-13, RF-14) ---
    def test_credit_note_purchase_creates_in_refund(self):
        """Wizard con digitized_document_type='nota_credito' (compra) -> in_refund."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'NC-001',
            'control_number': 'CTRL-NC-001',
            'invoice_date': '2026-08-15',
            'base_general': 500.0,
            'currency_id': self.env.company.currency_id.id,
            'digitized_document_type': 'nota_credito',
            'digitize_confidence': 0.92,
            'digitized_document_ref': 'FAC-ORIGINAL-001',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.move_type, 'in_refund')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'FAC-ORIGINAL-001')
        self.assertIn('[Digitalizado] tipo=nota_credito confianza=92%', move.narration)

    def test_credit_note_sale_creates_out_refund(self):
        """Wizard con digitized_document_type='nota_credito' (venta) -> out_refund."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'sale',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'NC-002',
            'control_number': 'CTRL-NC-002',
            'invoice_date': '2026-08-15',
            'base_general': 300.0,
            'currency_id': self.env.company.currency_id.id,
            'digitized_document_type': 'nota_credito',
            'digitize_confidence': 0.88,
            'digitized_document_ref': 'FAC-VENTA-005',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.move_type, 'out_refund')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'FAC-VENTA-005')
        self.assertIn('[Digitalizado] tipo=nota_credito confianza=88%', move.narration)

    def test_debit_note_purchase_creates_in_invoice_with_ref(self):
        """Wizard con digitized_document_type='nota_debito' (compra) -> in_invoice + ref."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'ND-001',
            'control_number': 'CTRL-ND-001',
            'invoice_date': '2026-08-15',
            'base_general': 200.0,
            'currency_id': self.env.company.currency_id.id,
            'digitized_document_type': 'nota_debito',
            'digitize_confidence': 0.91,
            'digitized_document_ref': 'FAC-ORIGINAL-002',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'FAC-ORIGINAL-002')
        self.assertIn('[Digitalizado] tipo=nota_debito confianza=91%', move.narration)

    def test_debit_note_sale_creates_out_invoice_with_ref(self):
        """Wizard con digitized_document_type='nota_debito' (venta) -> out_invoice + ref."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'sale',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'ND-002',
            'control_number': 'CTRL-ND-002',
            'invoice_date': '2026-08-15',
            'base_general': 150.0,
            'currency_id': self.env.company.currency_id.id,
            'digitized_document_type': 'nota_debito',
            'digitize_confidence': 0.85,
            'digitized_document_ref': 'FAC-VENTA-010',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.move_type, 'out_invoice')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'FAC-VENTA-010')
        self.assertIn('[Digitalizado] tipo=nota_debito confianza=85%', move.narration)

    def test_manual_flow_unchanged_no_digitized_fields(self):
        """Sin campos digitalizados -> comportamiento actual intacto (in_invoice/out_invoice)."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'FAC-MANUAL-001',
            'control_number': 'CTRL-MANUAL-001',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'currency_id': self.env.company.currency_id.id,
            # Sin digitized_document_type, digitize_confidence, digitized_document_ref
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'CTRL-MANUAL-001')
        # Narración no debe tener prefijo [Digitalizado]
        self.assertNotIn('[Digitalizado]', move.narration or '')

    def test_credit_note_narration_includes_digitized_info(self):
        """Narración de NC incluye tipo y confianza formateada."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'NC-003',
            'control_number': 'CTRL-NC-003',
            'invoice_date': '2026-08-15',
            'base_general': 100.0,
            'currency_id': self.env.company.currency_id.id,
            'concept': 'Devolución mercancía',
            'digitized_document_type': 'nota_credito',
            'digitize_confidence': 0.92,
            'digitized_document_ref': 'FAC-ORIGINAL-003',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        # Prefijo [Digitalizado] + tipo + confianza + separador + concept
        self.assertIn('[Digitalizado] tipo=nota_credito confianza=92%', move.narration)
        self.assertIn(' — Devolución mercancía', move.narration)

    def test_debit_note_narration_includes_digitized_info(self):
        """Narración de ND incluye tipo y confianza formateada."""
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': 'J-31527189-4',
            'invoice_number': 'ND-003',
            'control_number': 'CTRL-ND-003',
            'invoice_date': '2026-08-15',
            'base_general': 100.0,
            'currency_id': self.env.company.currency_id.id,
            'concept': 'Ajuste por diferencia',
            'digitized_document_type': 'nota_debito',
            'digitize_confidence': 0.87,
            'digitized_document_ref': 'FAC-ORIGINAL-004',
        })
        action = wizard.action_create_and_post()

        move_id = action.get('res_id')
        move = self.env['account.move'].browse(move_id)
        self.assertIn('[Digitalizado] tipo=nota_debito confianza=87%', move.narration)
        self.assertIn(' — Ajuste por diferencia', move.narration)

    # --- T5: RF-17 filtro por compañía ---
    def test_onchange_partner_vat_filters_by_company(self):
        """RF-17: _onchange_partner_vat no reutiliza partner de otra compañía."""
        rif = 'G-87654321-4'  # RIF válido
        partner_a = self.env['res.partner'].create({'name': 'Prov A', 'vat': rif})

        # Partner en otra compañía con mismo RIF
        company_b = self.env['res.company'].sudo().create({'name': 'Cía B'})
        self.env['res.partner'].sudo().create({
            'name': 'Prov B', 'vat': rif, 'company_id': company_b.id
        })

        # En compañía actual, onchange debe encontrar partner_a (no el de company_b)
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': rif,
            'invoice_number': 'FAC-ONCHANGE-001',
            'control_number': 'CTRL-ONCHANGE-001',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
        })
        wizard._onchange_partner_vat()
        self.assertEqual(wizard.partner_id, partner_a)

        # Si no hay partner en la compañía actual, no debe encontrar el de otra compañía
        partner_a.unlink()
        wizard2 = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': rif,
            'invoice_number': 'FAC-ONCHANGE-002',
            'control_number': 'CTRL-ONCHANGE-002',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
        })
        wizard2._onchange_partner_vat()
        self.assertFalse(wizard2.partner_id, "No debe reutilizar partner de otra compañía")

    def test_action_create_and_post_filters_partner_by_company(self):
        """RF-17: action_create_and_post no reutiliza partner de otra compañía."""
        rif = 'G-87654321-4'
        partner_a = self.env['res.partner'].create({'name': 'Prov A', 'vat': rif})

        # Partner en otra compañía con mismo RIF
        company_b = self.env['res.company'].sudo().create({'name': 'Cía B'})
        self.env['res.partner'].sudo().create({'name': 'Prov B', 'vat': rif, 'company_id': company_b.id})

        # En compañía actual, crea move con partner_a
        wizard = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': rif,
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
        })
        wizard._onchange_partner_vat()
        result = wizard.action_create_and_post()
        move = self.env['account.move'].browse(result['res_id'])
        self.assertEqual(move.partner_id, partner_a)

        # Usar un RIF diferente para probar creación automática sin partner existente
        rif2 = 'V-12345678-5'  # RIF válido diferente
        # Partner en otra compañía con este RIF
        self.env['res.partner'].sudo().create({'name': 'Prov C', 'vat': rif2, 'company_id': company_b.id})

        # En compañía actual, sin partner con rif2, debe crear uno nuevo (no usar el de company_b)
        wizard2 = self.env['l10n.ve.physical.invoice.wizard'].create({
            'type': 'purchase',
            'partner_vat': rif2,
            'invoice_number': 'FAC-002',
            'control_number': 'CTRL-002',
            'invoice_date': '2026-08-15',
            'base_general': 1000.0,
            'new_partner_name': 'Nuevo Prov Auto',
        })
        result2 = wizard2.action_create_and_post()
        move2 = self.env['account.move'].browse(result2['res_id'])
        # Debe crear un partner nuevo, no usar el de company_b
        self.assertNotEqual(move2.partner_id.company_id, company_b)
        self.assertEqual(move2.partner_id.name, 'Nuevo Prov Auto')
