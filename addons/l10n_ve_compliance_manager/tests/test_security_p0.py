"""Regresiones de los hallazgos P0 de la auditoría (2026-11-16).

Cubre:
- P0-03: el bot de ContaFis no debe tener una contraseña utilizable.
- P0-01/P0-02: aislamiento por compañía de cartelera, retenciones,
  planilla IVA y generador de libro.
- P0-02: el generador de libro deja de estar expuesto a ``base.group_user``.
"""

import os

from odoo.exceptions import AccessDenied, AccessError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

BOT_XMLID = 'l10n_ve_compliance_manager.user_contafis_bot'
LEGACY_BOT_PASSWORD = 'bot_unusable_password_123'


@tagged('post_install', '-at_install')
class TestSecurityP0BotCredentials(TransactionCase):
    """P0-03: el bot no puede autenticarse con la credencial filtrada."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot = cls.env.ref(BOT_XMLID, raise_if_not_found=False)

    def test_bot_exists(self):
        self.assertTrue(self.bot, 'El usuario bot del módulo debe existir.')

    def test_bot_has_no_password(self):
        self.assertTrue(self.bot)
        # ``password`` is a computed field, so it always reads as empty.
        # Check the stored hash directly.
        self.env.cr.execute(
            'SELECT password FROM res_users WHERE id = %s', (self.bot.id,),
        )
        self.assertIsNone(
            self.env.cr.fetchone()[0],
            'El bot no debe tener contraseña almacenada.',
        )

    def test_legacy_bot_password_cannot_authenticate(self):
        self.assertTrue(self.bot)
        with self.assertRaises(AccessDenied):
            self.env['res.users'].authenticate(
                {
                    'type': 'password',
                    'login': self.bot.login,
                    'password': LEGACY_BOT_PASSWORD,
                },
                {},
            )

    def test_bot_data_file_has_no_password_field(self):
        module_path = get_module_path('l10n_ve_compliance_manager')
        self.assertTrue(module_path)
        path = os.path.join(module_path, 'data', 'res_users_data.xml')
        with open(path, encoding='utf-8') as handle:
            content = handle.read()
        self.assertNotIn(LEGACY_BOT_PASSWORD, content)
        self.assertNotIn('<field name="password">', content)


@tagged('post_install', '-at_install')
class TestSecurityP0CompanyIsolation(TransactionCase):
    """P0-01/P0-02: ningún modelo filtra registros de otra compañía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'P0 Isolation B'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

        cls.partner_a = cls.env['res.partner'].create({'name': 'P0 Partner A'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'P0 Partner B'})
        Client = cls.env['l10n.ve.compliance.client']
        cls.client_a = Client.create({
            'name': 'P0 Client A',
            'partner_id': cls.partner_a.id,
            'company_id': cls.company_a.id,
        })
        cls.client_b = Client.create({
            'name': 'P0 Client B',
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_b.id,
        })

        cls.document_type = cls.env['l10n.ve.document.type'].create({
            'name': 'P0 Document Type',
            'code': 'P0T',
        })
        status_vals = {
            'year': 2026,
            'month': '1',
            'document_type_id': cls.document_type.id,
            'state': 'valid',
        }
        Status = cls.env['l10n.ve.cartelera.status']
        cls.status_a = Status.create(dict(status_vals, client_id=cls.client_a.id))
        cls.status_b = Status.create(dict(status_vals, client_id=cls.client_b.id))

        Evidence = cls.env['l10n.ve.cartelera.evidence']
        cls.evidence_a = Evidence.create({'cartelera_status_id': cls.status_a.id})
        cls.evidence_b = Evidence.create({'cartelera_status_id': cls.status_b.id})

        Retention = cls.env['l10n.retention']
        cls.retention_a = Retention.create({
            'company_id': cls.company_a.id,
            'name': 'P0-RET-A',
        })
        cls.retention_b = Retention.create({
            'company_id': cls.company_b.id,
            'name': 'P0-RET-B',
        })

        VatReturn = cls.env['l10n.ve.vat.return']
        cls.vat_return_a = VatReturn.create({
            'company_id': cls.company_a.id,
            'period_month': '2026-01',
        })
        cls.vat_return_b = VatReturn.create({
            'company_id': cls.company_b.id,
            'period_month': '2026-01',
        })

        Generate = cls.env['l10n.ve.vat.book.generate']
        cls.generate_a = Generate.create({
            'company_id': cls.company_a.id,
            'period_month': '2026-01',
            'book_type': 'both',
        })
        cls.generate_b = Generate.create({
            'company_id': cls.company_b.id,
            'period_month': '2026-01',
            'book_type': 'both',
        })

    def _as_company(self, model_name, company):
        return self.env[model_name].with_user(self.admin).with_context(
            allowed_company_ids=[company.id],
        )

    def _assert_isolated(self, model_name, record_a, record_b):
        in_a = self._as_company(model_name, self.company_a)
        in_b = self._as_company(model_name, self.company_b)
        self.assertIn(record_a, in_a.search([]))
        self.assertNotIn(record_b, in_a.search([]))
        self.assertIn(record_b, in_b.search([]))
        self.assertNotIn(record_a, in_b.search([]))

    def test_cartelera_status_isolated_by_company(self):
        self._assert_isolated('l10n.ve.cartelera.status', self.status_a, self.status_b)

    def test_cartelera_evidence_isolated_by_company(self):
        self._assert_isolated(
            'l10n.ve.cartelera.evidence', self.evidence_a, self.evidence_b,
        )

    def test_retention_isolated_by_company(self):
        self._assert_isolated('l10n.retention', self.retention_a, self.retention_b)

    def test_vat_return_isolated_by_company(self):
        self._assert_isolated(
            'l10n.ve.vat.return', self.vat_return_a, self.vat_return_b,
        )

    def test_vat_book_generate_isolated_by_company(self):
        self._assert_isolated(
            'l10n.ve.vat.book.generate', self.generate_a, self.generate_b,
        )

    def test_cartelera_company_id_is_related(self):
        self.assertEqual(self.status_a.company_id, self.company_a)
        self.assertEqual(self.status_b.company_id, self.company_b)
        self.assertEqual(self.evidence_a.company_id, self.company_a)
        self.assertEqual(self.evidence_b.company_id, self.company_b)

    def test_cross_company_read_is_denied(self):
        cases = [
            ('l10n.ve.cartelera.status', self.status_b),
            ('l10n.ve.cartelera.evidence', self.evidence_b),
            ('l10n.retention', self.retention_b),
            ('l10n.ve.vat.return', self.vat_return_b),
            ('l10n.ve.vat.book.generate', self.generate_b),
        ]
        for model_name, record in cases:
            with self.subTest(model=model_name):
                in_a = self._as_company(model_name, self.company_a)
                with self.assertRaises(AccessError):
                    in_a.browse(record.id).read(['id'])


@tagged('post_install', '-at_install')
class TestSecurityP0VatBookGenerateAcl(TransactionCase):
    """P0-02: el generador de libro ya no está abierto a todo usuario interno."""

    def _create_user(self, login, group_xmlids):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [self.env.ref(xmlid).id for xmlid in group_xmlids])],
        })

    def test_account_user_cannot_create_generate_record(self):
        billing = self._create_user('p0_billing', ['account.group_account_user'])
        with self.assertRaises(AccessError):
            self.env['l10n.ve.vat.book.generate'].with_user(billing).create({
                'company_id': self.env.company.id,
                'period_month': '2026-01',
                'book_type': 'both',
            })

    def test_account_manager_can_create_generate_record(self):
        manager = self._create_user('p0_manager', ['account.group_account_manager'])
        record = self.env['l10n.ve.vat.book.generate'].with_user(manager).create({
            'company_id': self.env.company.id,
            'period_month': '2026-01',
            'book_type': 'both',
        })
        self.assertTrue(record.exists())
