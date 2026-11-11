from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyDigitize(TransactionCase):
    """Aislamiento por compañía en wizards de digitalización y factura física."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({
            'name': 'Compañía B Digitización',
            'country_id': cls.env.ref('base.ve').id,
            'currency_id': cls.env.ref('base.VEF').id,
        })
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

        # Impuestos y diario de compra para compañía B
        cls.country = cls.env.ref('base.ve')
        cls.env['account.chart.template'].try_loading('ve', cls.company_b, install_demo=False)
        cls._ensure_vat_taxes(company=cls.company_b, country=cls.country)

        cls.journal_b = cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', cls.company_b.id),
        ], limit=1)
        cls.account_expense_b = cls.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [cls.company_b.id]),
        ], limit=1)
        cls.journal_b.write({'default_account_id': cls.account_expense_b.id})

        # Partner de B con RIF válido (módulo 11)
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Proveedor B',
            'vat': 'J-31527189-4',
            'company_id': cls.company_b.id,
        })

        # Partner compartido en A para test de regresión (una sola compañía)
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Proveedor A',
            'vat': 'J-50025738-5',
            'company_id': cls.company_a.id,
        })

    @classmethod
    def _ensure_vat_taxes(cls, company, country):
        """Crea (o reutiliza) impuestos SENIAT de la compañía para el test."""
        group = cls.env['account.tax.group'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if not group:
            group = cls.env['account.tax.group'].create({
                'name': 'IVA', 'country_id': country.id,
            })
        elif group.country_id.id != country.id:
            group.write({'country_id': country.id})

        taxes = cls.env['account.tax']
        for tax_type, amount, use, name in (
            ('general', 16.0, 'purchase', 'IVA General 16% (Compra)'),
            ('general', 16.0, 'sale', 'IVA General 16% (Venta)'),
        ):
            tax = cls.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', tax_type),
                ('type_tax_use', '=', use),
                ('company_id', '=', company.id),
            ], limit=1)
            if not tax:
                tax = cls.env['account.tax'].create({
                    'name': name,
                    'amount_type': 'percent',
                    'amount': amount,
                    'l10n_ve_tax_type': tax_type,
                    'type_tax_use': use,
                    'company_id': company.id,
                    'tax_group_id': group.id,
                    'country_id': country.id,
                })
            taxes |= tax

    def _as_admin_in_a(self, record):
        """Ejecuta record como admin con compañía A activa."""
        return record.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id],
        )

    def test_physical_invoice_non_active_company(self):
        """Crear y postear factura física para Compañía B estando en A."""
        Wizard = self.env['l10n.ve.physical.invoice.wizard']
        wizard = Wizard.create({
            'company_id': self.company_b.id,
            'currency_id': self.company_b.currency_id.id,
            'type': 'purchase',
            'partner_vat': self.partner_b.vat,
            'invoice_number': 'B-DIG-001',
            'control_number': 'B-CTRL-001',
            'invoice_date': '2031-06-15',
            'invoice_date_due': '2031-06-30',
            'base_general': 1000.0,
        })

        # Ejecutar como admin con A activa
        action = self._as_admin_in_a(wizard).action_create_and_post()
        move = self.env['account.move'].browse(action['res_id'])

        self.assertEqual(move.company_id, self.company_b)
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.amount_total, 1160.0)

        # Línea de libro IVA debe heredar company_id = B
        book_line = self.env['l10n.ve.vat.book.line'].search([
            ('account_move_id', '=', move.id),
        ])
        self.assertTrue(book_line, "Se esperaba al menos una línea de libro IVA")
        self.assertEqual(book_line.company_id, self.company_b)
        self.assertEqual(book_line.book_type, 'purchase')
        self.assertEqual(book_line.operation_code, '33')
        self.assertGreater(book_line.base_general, 0.0)
        self.assertGreater(book_line.vat_general, 0.0)

    def test_digitize_wizard_currency_defaults_use_wizard_company(self):
        """Defaults de moneda y company_id usan la compañía del wizard, no la activa."""
        Wizard = self.env['l10n.ve.digitize.wizard']
        wizard = Wizard.create({
            'company_id': self.company_b.id,
            'type': 'purchase',
        })

        defaults = wizard._map_extracted_to_invoice_defaults({'currency': 'VES'})
        self.assertEqual(defaults['default_currency_id'], self.company_b.currency_id.id)
        self.assertEqual(defaults['default_company_id'], self.company_b.id)

        defaults_usd = wizard._map_extracted_to_invoice_defaults({'currency': 'USD'})
        self.assertEqual(defaults_usd['default_company_id'], self.company_b.id)

    def test_digitize_wizard_partner_search_uses_wizard_company(self):
        """Búsqueda de partner usa compañía del wizard, no la activa."""
        Wizard = self.env['l10n.ve.digitize.wizard']
        wizard = Wizard.create({
            'company_id': self.company_b.id,
            'type': 'purchase',
        })

        # Partner de B existe con RIF válido; también podría existir uno de A con mismo VAT
        defaults = wizard._map_extracted_to_invoice_defaults({
            'supplier_rif': self.partner_b.vat,
        })
        self.assertEqual(defaults['default_partner_id'], self.partner_b.id)
        self.assertEqual(defaults['default_partner_vat'], self.partner_b.vat)

    def test_physical_invoice_active_company_unchanged(self):
        """Regresión: flujo con compañía activa sigue funcionando."""
        Wizard = self.env['l10n.ve.physical.invoice.wizard']
        wizard = Wizard.create({
            'company_id': self.company_a.id,
            'currency_id': self.company_a.currency_id.id,
            'type': 'purchase',
            'partner_vat': self.partner_a.vat,
            'invoice_number': 'A-DIG-001',
            'control_number': 'A-CTRL-001',
            'invoice_date': '2031-06-15',
            'invoice_date_due': '2031-06-30',
            'base_general': 1000.0,
        })

        move = wizard.action_create_and_post()
        if isinstance(move, dict):
            move = self.env['account.move'].browse(move['res_id'])

        self.assertEqual(move.company_id, self.company_a)
        self.assertEqual(move.state, 'posted')
