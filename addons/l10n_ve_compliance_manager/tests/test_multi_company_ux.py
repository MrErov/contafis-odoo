from lxml import etree
from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestMultiCompanyUx(TransactionCase):
    """Cierra brechas de UX multi-compañía en wizards de importación y libros."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía UX 008D'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

    def _as_admin_in_a(self, record):
        """Ejecuta record como admin con compañía A activa."""
        return record.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id],
        )

    def _create_wizard(self, import_type, company_id, **vals):
        """Crea un wizard de importación en modo lax para la compañía dada."""
        base = {
            'import_type': import_type,
            'company_id': company_id.id,
            'mode': 'lax',
        }
        base.update(vals)
        return self.env['l10n.ve.import.wizard'].create(base)

    def _map(self, wizard, field_name, field_type, relation_model=''):
        """Crea un mapeo de columna con índice y letra incrementales."""
        index = len(wizard.mapping_ids)
        return self.env['l10n.ve.import.mapping'].create({
            'wizard_id': wizard.id,
            'col_index': index,
            'column_letter': chr(ord('A') + index),
            'col_name': field_name,
            'field_name': field_name,
            'field_type': field_type,
            'relation_model': relation_model,
            'required': True,
        })

    def _line(self, wizard, data, row_index=1):
        """Crea una línea de importación en borrador con los datos dados."""
        return self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': row_index,
            'data': data,
            'state': 'draft',
        })

    def _client(self, company, name, rif):
        """Crea partner y cliente de cumplimiento en la compañía indicada."""
        partner = self.env['res.partner'].create({
            'name': name,
            'company_id': company.id,
        })
        return self.env['l10n.ve.compliance.client'].create({
            'name': name,
            'partner_id': partner.id,
            'company_id': company.id,
            'rif': rif,
        })

    def _purchase_journal(self, company, code, name):
        """Devuelve (o crea) un diario de compras con cuenta de gastos."""
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', company.id),
        ], limit=1)
        if journal:
            return journal
        account = self.env['account.account'].with_company(company).create({
            'name': f'Gastos {name}',
            'code': code,
            'account_type': 'expense',
            'company_ids': [(6, 0, [company.id])],
        })
        return self.env['account.journal'].with_company(company).create({
            'name': name,
            'code': code[:5],
            'type': 'purchase',
            'company_id': company.id,
            'default_account_id': account.id,
        })

    def _draft_bill(self, company, journal, partner, name):
        """Crea una factura de proveedor borrador con nombre fijo."""
        move = self.env['account.move'].with_company(company).create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': fields.Date.to_date('2031-06-01'),
        })
        move.write({'name': name})
        return move

    def _retention_sequence(self, company):
        """Asegura la secuencia de retenciones de la compañía.

        El dato de `ir.sequence` se carga con la compañía principal, así que
        una compañía nueva necesita su propia secuencia numérica.
        """
        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'l10n.retention'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': 'Retención',
                'code': 'l10n.retention',
                'prefix': 'RET-%(year)s-',
                'padding': 4,
                'company_id': company.id,
            })
        return sequence

    def test_retention_import_resolves_currency_and_invoice(self):
        """Resolver currency_id e invoice_id desde texto en la compañía del wizard."""
        partner_b = self.env['res.partner'].create({
            'name': 'Proveedor UX 008D',
            'company_id': self.company_b.id,
        })
        journal_b = self._purchase_journal(
            self.company_b, 'UXPB', 'Compras UX 008D',
        )
        move_b = self._draft_bill(
            self.company_b, journal_b, partner_b, 'UXD-BILL-0001',
        )
        self.assertEqual(
            move_b.name, 'UXD-BILL-0001',
            'El nombre de la factura de B debe quedar fijado para el test',
        )

        currency = self.env['res.currency'].with_context(active_test=False).search([
            ('name', 'in', ['USD', 'EUR']),
            ('id', '!=', self.company_b.currency_id.id),
        ], limit=1)
        self.assertTrue(currency, 'Debe existir USD o EUR en la BD')
        if not currency.active:
            currency.active = True
        self.assertNotEqual(currency, self.company_b.currency_id)

        # Decoy en A con el mismo número de factura: sin filtro de compañía
        # el search por nombre devolvería primero la de A (id menor).
        journal_a = self._purchase_journal(
            self.company_a, 'UXPA', 'Compras UX 008D A',
        )
        partner_a = self.env['res.partner'].create({
            'name': 'Proveedor Decoy UX 008D',
            'company_id': self.company_a.id,
        })
        decoy_a = self._draft_bill(
            self.company_a, journal_a, partner_a, 'UXD-BILL-0001',
        )
        self.assertNotEqual(decoy_a, move_b)

        self._retention_sequence(self.company_b)
        wizard = self._create_wizard('retention', self.company_b)
        self._map(wizard, 'partner_id', 'many2one', 'res.partner')
        self._map(wizard, 'amount', 'float')
        self._map(wizard, 'currency_id', 'many2one', 'res.currency')
        self._map(wizard, 'date', 'date')
        self._map(wizard, 'invoice_id', 'many2one', 'account.move')
        line = self._line(wizard, {
            'partner_id': partner_b.name,
            'amount': 1500.0,
            'currency_id': currency.name,
            'date': '2031-06-15',
            'invoice_id': 'UXD-BILL-0001',
        })

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(
            line.state, 'imported',
            f'La línea debió importarse; error: {line.error_msg}',
        )
        retention = self.env['l10n.retention'].sudo().search([
            ('invoice_id', '=', move_b.id),
        ])
        self.assertEqual(len(retention), 1)
        self.assertEqual(retention.currency_id, currency)
        self.assertEqual(retention.partner_id, partner_b)
        self.assertNotEqual(retention.invoice_id, decoy_a)

    def test_unresolved_many2one_reports_clear_error(self):
        """Un Many2one inexistente reporta un error de negocio legible."""
        wizard = self._create_wizard('retention', self.company_b)
        self._map(wizard, 'currency_id', 'many2one', 'res.currency')
        line = self._line(wizard, {'currency_id': 'ZZZ'})

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(line.state, 'error')
        self.assertIn('No se encontró', line.error_msg or '')
        self.assertIn('ZZZ', line.error_msg or '')

    def test_validate_reference_matches_resolve_values(self):
        """validate_reference usa el mismo criterio de búsqueda que el import."""
        name = 'Cliente UX F2'
        client_b = self._client(self.company_b, name, 'J-80000901-1')
        decoy_a = self._client(self.company_a, name, 'J-80000900-0')
        self.assertNotEqual(client_b, decoy_a)

        wizard = self._create_wizard('obligation', self.company_b)
        self._map(wizard, 'client_id', 'many2one', 'l10n.ve.compliance.client')
        line = self._line(wizard, {'client_id': name})

        self.assertTrue(
            line._validate_reference(),
            f'El cliente de B debe encontrarse por nombre; error: {line.error_msg}',
        )
        self.assertNotEqual(line.state, 'error')
        self.assertNotIn('Referencia no encontrada', line.error_msg or '')

        with self.subTest('partner compartido por nombre'):
            shared = self.env['res.partner'].create({
                'name': 'Proveedor Compartido UX F2',
                'company_id': False,
            })
            wizard_2 = self._create_wizard('obligation', self.company_b)
            self._map(wizard_2, 'partner_id', 'many2one', 'res.partner')
            line_2 = self._line(
                wizard_2, {'partner_id': shared.name}, row_index=2,
            )
            self.assertTrue(
                line_2._validate_reference(),
                f'El partner compartido debe encontrarse; error: {line_2.error_msg}',
            )

    def test_validate_reference_rejects_foreign_company_records(self):
        """Un partner exclusivo de otra compañía no es una referencia válida."""
        foreign = self.env['res.partner'].create({
            'name': 'Proveedor Solo A UX',
            'company_id': self.company_a.id,
        })
        wizard = self._create_wizard('retention', self.company_b)
        self._map(wizard, 'partner_id', 'many2one', 'res.partner')
        line = self._line(wizard, {'partner_id': foreign.name})

        self.assertFalse(
            line._validate_reference(),
            'Un partner de A no debe resolver en un wizard de B',
        )
        self.assertEqual(line.state, 'error')
        self.assertIn('Referencia no encontrada', line.error_msg or '')

    def test_import_target_domains_include_wizard_company(self):
        """La clave única de obligaciones y documentos filtra por compañía."""
        client_b = self._client(self.company_b, 'Cliente UX F3', 'J-80000902-2')
        obligation_type = self.env['l10n.ve.obligation.type'].create({
            'name': 'Tipo UX F3',
        })
        wizard = self._create_wizard('obligation', self.company_b)
        line = self._line(wizard, {
            'client_id': client_b.id,
            'obligation_type_id': obligation_type.id,
            'period': '08/2031',
        })

        model_name, domain = wizard._get_import_target(line, {
            'client_id': client_b.id,
            'obligation_type_id': obligation_type.id,
            'period': '08/2031',
        })
        self.assertEqual(model_name, 'l10n.ve.obligation')
        self.assertIn(
            ('client_id.company_id', '=', self.company_b.id), domain,
            'La clave única debe acotarse a la compañía del cliente',
        )

        with self.subTest('documentos'):
            document_type = self.env['l10n.ve.document.type'].create({
                'name': 'Doc UX F3',
                'code': 'UXF3',
            })
            wizard_doc = self._create_wizard('document', self.company_b)
            line_doc = self._line(wizard_doc, {
                'client_id': client_b.id,
                'document_type_id': document_type.id,
                'number': 'UX-F3-001',
            })
            model_name_doc, domain_doc = wizard_doc._get_import_target(
                line_doc,
                {
                    'client_id': client_b.id,
                    'document_type_id': document_type.id,
                    'number': 'UX-F3-001',
                },
            )
            self.assertEqual(model_name_doc, 'l10n.ve.document')
            self.assertIn(
                ('client_id.company_id', '=', self.company_b.id), domain_doc,
                'La clave única debe acotarse a la compañía del cliente',
            )

    def test_navigation_actions_carry_allowed_company_ids(self):
        """Las acciones de navegación propagan las compañías permitidas."""
        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2031-07',
            'company_id': self.company_b.id,
        })
        action = vat_return.action_open_book_lines()
        self.assertIn(
            'context', action,
            'La acción debe propagar contexto de compañías',
        )
        self.assertIn(
            self.company_b.id, action['context'].get('allowed_company_ids', []),
        )

        partner_b = self.env['res.partner'].create({
            'name': 'Proveedor UX F6',
            'company_id': self.company_b.id,
        })
        journal_b = self._purchase_journal(
            self.company_b, 'UXP6', 'Compras UX F6',
        )
        move_b = self._draft_bill(
            self.company_b, journal_b, partner_b, 'UXD-BILL-0006',
        )
        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2031-07',
            'company_id': self.company_b.id,
            'book_type': 'both',
        })
        wizard.write({'move_ids': [(6, 0, [move_b.id])]})
        action = wizard.action_generate()
        self.assertIn(
            self.company_b.id, action['context'].get('allowed_company_ids', []),
        )
        self.assertEqual(
            action['context'].get('search_default_group_by_book_type'), 1,
        )

    def test_reset_actions_carry_allowed_company_ids(self):
        """Los reinicios de wizard devuelven la compañía permitida."""
        wizard = self.env['l10n.ve.vat.book.generate'].create({
            'period_month': '2031-08',
            'company_id': self.company_b.id,
            'book_type': 'both',
        })
        action = wizard.action_reset()
        self.assertIn(
            'context', action,
            'El reinicio del libro debe propagar contexto de compañías',
        )
        self.assertIn(
            self.company_b.id, action['context'].get('allowed_company_ids', []),
        )

        import_wizard = self._create_wizard('obligation', self.company_b)
        action = import_wizard.action_reset()
        self.assertIn(
            'context', action,
            'El reinicio del importador debe propagar contexto de compañías',
        )
        self.assertIn(
            self.company_b.id, action['context'].get('allowed_company_ids', []),
        )


@tagged('post_install', '-at_install')
class TestWizardCompanyFieldDomains(TransactionCase):
    """Los campos compañía de los wizards sólo ofrecen compañías permitidas."""

    def test_wizard_company_field_domain_restricts_allowed_companies(self):
        """Cada campo company_id declara el domain de compañías permitidas."""
        xmlids = [
            'l10n_ve_compliance_manager.view_l10n_ve_import_wizard_form',
            'l10n_ve_compliance_manager.view_l10n_ve_vat_book_export_wizard_form',
            'l10n_ve_compliance_manager.view_l10n_ve_vat_book_generate_form',
        ]
        for xmlid in xmlids:
            view = self.env.ref(xmlid)
            arch = etree.fromstring(view.arch.encode())
            nodes = arch.findall(".//field[@name='company_id']")
            self.assertEqual(
                len(nodes), 1,
                f'{xmlid} debe declarar exactamente un field company_id',
            )
            domain = nodes[0].get('domain') or ''
            self.assertIn(
                'allowed_company_ids', domain,
                f'{xmlid} debe restringir company_id a allowed_company_ids',
            )
            self.assertEqual(
                safe_eval(domain, {'allowed_company_ids': [1]}),
                [('id', 'in', [1])],
            )
