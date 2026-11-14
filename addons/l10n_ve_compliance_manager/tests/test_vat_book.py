from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestVatBookCompanyIsolation(TransactionCase):
    """Aislamiento por compañía de las líneas del Libro de Compras/Ventas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía Libro IVA'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Partner Libro IVA A',
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Partner Libro IVA B',
            'company_id': cls.company_b.id,
        })
        cls.line_a = cls.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2031-01',
            'partner_id': cls.partner_a.id,
            'invoice_number': 'VC-ISO-A',
            'control_number': 'VC-ISO-A',
            'operation_code': '33',
            'company_id': cls.company_a.id,
        })
        cls.line_b = cls.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2031-01',
            'partner_id': cls.partner_b.id,
            'invoice_number': 'VC-ISO-B',
            'control_number': 'VC-ISO-B',
            'operation_code': '33',
            'company_id': cls.company_b.id,
        })

    def test_vat_book_action_filters_by_company(self):
        """La acción filtra por la compañía activa vía allowed_company_ids."""
        action = self.env.ref('l10n_ve_compliance_manager.action_l10n_ve_vat_book_line')
        self.assertEqual(action.res_model, 'l10n.ve.vat.book.line')
        self.assertTrue(action.domain)
        self.assertIn('company_id', action.domain)
        self.assertIn('allowed_company_ids', action.domain)

        # sudo para aislar la capa acción de la regla ORM
        VatBookLine = self.env['l10n.ve.vat.book.line'].sudo()
        domain_a = safe_eval(action.domain, {'allowed_company_ids': [self.company_a.id]})
        records_a = VatBookLine.search(domain_a)
        self.assertIn(self.line_a, records_a)
        self.assertNotIn(self.line_b, records_a)

        domain_b = safe_eval(action.domain, {'allowed_company_ids': [self.company_b.id]})
        records_b = VatBookLine.search(domain_b)
        self.assertIn(self.line_b, records_b)
        self.assertNotIn(self.line_a, records_b)

        domain_both = safe_eval(
            action.domain,
            {'allowed_company_ids': [self.company_a.id, self.company_b.id]},
        )
        records_both = VatBookLine.search(domain_both)
        self.assertIn(self.line_a, records_both)
        self.assertIn(self.line_b, records_both)

    def test_vat_book_lines_isolated_between_companies(self):
        """La regla ORM aísla las líneas entre compañías."""
        VatBookLine = self.env['l10n.ve.vat.book.line']

        records_a = VatBookLine.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id],
        ).search([])
        self.assertIn(self.line_a, records_a)
        self.assertNotIn(self.line_b, records_a)
        self.assertTrue(all(record.company_id == self.company_a for record in records_a))

        records_b = VatBookLine.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_b.id],
        ).search([])
        self.assertIn(self.line_b, records_b)
        self.assertNotIn(self.line_a, records_b)
        self.assertEqual(records_b, self.line_b)

        records_both = VatBookLine.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id],
        ).search([])
        self.assertIn(self.line_a, records_both)
        self.assertIn(self.line_b, records_both)

    def test_vat_book_line_company_rule_is_global(self):
        """La regla de compañía existe, es global y usa company_ids."""
        rule = self.env.ref(
            'l10n_ve_compliance_manager.rule_l10n_ve_vat_book_line_company',
        )
        self.assertEqual(rule.model_id.model, 'l10n.ve.vat.book.line')
        self.assertEqual(rule.domain_force, "[('company_id', 'in', company_ids)]")
        self.assertFalse(rule.groups)
