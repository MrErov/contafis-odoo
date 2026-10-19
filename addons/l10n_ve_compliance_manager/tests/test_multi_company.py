from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyIsolation(TransactionCase):
    """Aislamiento por compañía de los registros del módulo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía Aislamiento'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

        cls.client_a = cls.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Aislamiento A',
            'partner_id': cls.env['res.partner'].create({'name': 'Partner Aislamiento A'}).id,
            'company_id': cls.company_a.id,
        })
        cls.client_b = cls.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Aislamiento B',
            'partner_id': cls.env['res.partner'].create({'name': 'Partner Aislamiento B'}).id,
            'company_id': cls.company_b.id,
        })
        cls.obligation_a = cls.env['l10n.ve.obligation'].create({
            'name': 'Obligación Aislamiento A',
            'client_id': cls.client_a.id,
        })
        cls.obligation_b = cls.env['l10n.ve.obligation'].create({
            'name': 'Obligación Aislamiento B',
            'client_id': cls.client_b.id,
        })
        cls.document_a = cls.env['l10n.ve.document'].create({'client_id': cls.client_a.id})
        cls.document_b = cls.env['l10n.ve.document'].create({'client_id': cls.client_b.id})
        cls.alert_a = cls.env['l10n.ve.alert'].create({
            'name': 'Alerta Aislamiento A',
            'client_id': cls.client_a.id,
        })
        cls.alert_b = cls.env['l10n.ve.alert'].create({
            'name': 'Alerta Aislamiento B',
            'client_id': cls.client_b.id,
        })

    def _for_company(self, model_name, company):
        return self.env[model_name].with_user(self.admin).with_context(
            allowed_company_ids=[company.id],
        )

    def test_client_isolated_by_company(self):
        in_a = self._for_company('l10n.ve.compliance.client', self.company_a)
        in_b = self._for_company('l10n.ve.compliance.client', self.company_b)
        self.assertIn(self.client_a, in_a.search([]))
        self.assertNotIn(self.client_b, in_a.search([]))
        self.assertIn(self.client_b, in_b.search([]))
        self.assertNotIn(self.client_a, in_b.search([]))

    def test_obligation_isolated_by_company(self):
        in_a = self._for_company('l10n.ve.obligation', self.company_a)
        in_b = self._for_company('l10n.ve.obligation', self.company_b)
        self.assertIn(self.obligation_a, in_a.search([]))
        self.assertNotIn(self.obligation_b, in_a.search([]))
        self.assertIn(self.obligation_b, in_b.search([]))
        self.assertNotIn(self.obligation_a, in_b.search([]))

    def test_document_isolated_by_company(self):
        in_a = self._for_company('l10n.ve.document', self.company_a)
        in_b = self._for_company('l10n.ve.document', self.company_b)
        self.assertIn(self.document_a, in_a.search([]))
        self.assertNotIn(self.document_b, in_a.search([]))
        self.assertIn(self.document_b, in_b.search([]))
        self.assertNotIn(self.document_a, in_b.search([]))

    def test_alert_isolated_by_company(self):
        in_a = self._for_company('l10n.ve.alert', self.company_a)
        in_b = self._for_company('l10n.ve.alert', self.company_b)
        self.assertIn(self.alert_a, in_a.search([]))
        self.assertNotIn(self.alert_b, in_a.search([]))
        self.assertIn(self.alert_b, in_b.search([]))
        self.assertNotIn(self.alert_a, in_b.search([]))

    def test_user_with_two_companies_sees_both(self):
        both = self.env['l10n.ve.compliance.client'].with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id],
        )
        records = both.search([])
        self.assertIn(self.client_a, records)
        self.assertIn(self.client_b, records)

    def test_new_client_defaults_to_active_company(self):
        client = self.env['l10n.ve.compliance.client'].with_user(self.admin).with_company(
            self.company_b
        ).create({
            'name': 'Cliente Aislamiento Default',
            'partner_id': self.env['res.partner'].create({'name': 'Partner Default'}).id,
        })
        self.assertEqual(client.company_id, self.company_b)
