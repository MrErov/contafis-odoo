import base64
from pathlib import Path

from odoo.tests import TransactionCase, tagged

FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx'


@tagged('post_install', '-at_install')
class TestMultiCompanyImportIslr(TransactionCase):
    """Aislamiento por compañía del import genérico y la conciliación ISLR."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía Import ISLR'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

    def _as_admin_in_a(self, record):
        """Ejecuta record como admin con compañía A activa."""
        return record.with_user(self.admin).with_context(
            allowed_company_ids=[self.company_a.id],
        )

    def _search_as_admin_in_b(self, model, domain=None, **kwargs):
        """Busca como admin con compañía B activa (para verificación)."""
        return self.env[model].with_user(self.admin).with_context(
            allowed_company_ids=[self.company_b.id],
        ).search(domain or [], **kwargs)

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

    def test_import_client_non_active_company(self):
        """Importar clientes para B con A activa sin mezclar RIF homónimos."""
        partner_b = self.env['res.partner'].create({
            'name': 'Proveedor Único MC 008C',
            'company_id': self.company_b.id,
        })
        decoy_a = self._client(
            self.company_a, 'Cliente Decoy MC 008C', 'J-80000801-1',
        )

        wizard = self._create_wizard('client', self.company_b)
        self._map(wizard, 'name', 'char')
        self._map(wizard, 'partner_id', 'many2one', 'res.partner')
        self._map(wizard, 'rif', 'char')
        line = self._line(wizard, {
            'name': 'Cliente Importado MC',
            'partner_id': 'Proveedor Único MC 008C',
            'rif': 'J-80000801-1',
        })

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(line.state, 'imported')
        self.assertFalse(line.error_msg)

        clients_b = self._search_as_admin_in_b('l10n.ve.compliance.client', [
            ('rif', '=', 'J-80000801-1'),
            ('company_id', '=', self.company_b.id),
        ])
        self.assertEqual(len(clients_b), 1, 'Debe existir exactamente 1 cliente en B')
        self.assertEqual(clients_b.partner_id, partner_b)
        self.assertEqual(clients_b.company_id, self.company_b)

        clients_a = self.env['l10n.ve.compliance.client'].sudo().search([
            ('rif', '=', 'J-80000801-1'),
            ('company_id', '=', self.company_a.id),
        ])
        self.assertEqual(len(clients_a), 1, 'El decoy de A debe seguir intacto')
        self.assertEqual(clients_a, decoy_a)

    def test_import_client_resolves_partner_in_wizard_company(self):
        """Resolver partner_id dentro de la compañía del wizard, no en la activa."""
        name = 'Proveedor Homónimo MC 008C'
        decoy_a1 = self.env['res.partner'].create({
            'name': name,
            'vat': 'J-80000802-2',
            'company_id': self.company_a.id,
        })
        partner_b = self.env['res.partner'].create({
            'name': name,
            'vat': 'J-80000803-3',
            'company_id': self.company_b.id,
        })
        decoy_a2 = self.env['res.partner'].create({
            'name': name,
            'vat': 'J-80000804-4',
            'company_id': self.company_a.id,
        })

        visible = self.env['res.partner'].with_user(self.admin).with_context(
            allowed_company_ids=[self.company_b.id, self.company_a.id],
        ).search([('name', '=', name)])
        self.assertIn(decoy_a1, visible)
        self.assertIn(decoy_a2, visible)

        wizard = self._create_wizard('client', self.company_b)
        self._map(wizard, 'name', 'char')
        self._map(wizard, 'partner_id', 'many2one', 'res.partner')
        self._map(wizard, 'rif', 'char')
        line = self._line(wizard, {
            'name': 'Cliente Homónimo MC',
            'partner_id': name,
            'rif': 'J-80000806-6',
        })

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(line.state, 'imported')
        client = self._search_as_admin_in_b('l10n.ve.compliance.client', [
            ('rif', '=', 'J-80000806-6'),
        ], limit=1)
        self.assertEqual(len(client), 1)
        self.assertEqual(
            client.partner_id,
            partner_b,
            'partner_id debe ser de la compañía del wizard; se resolvió '
            f'{client.partner_id.name} ({client.partner_id.company_id.name})',
        )
        self.assertNotEqual(client.partner_id, decoy_a1)
        self.assertNotEqual(client.partner_id, decoy_a2)

    def test_import_obligation_non_active_company(self):
        """Importar obligaciones para el cliente de B sin tocar el decoy de A."""
        # El decoy de A se crea primero (id menor): sin el filtro de compañía
        # en `_resolve_values`, el search por nombre devolvería el de A.
        client_a = self._client(
            self.company_a, 'Cliente MC Obligaciones', 'J-80000807-7',
        )
        client_b = self._client(
            self.company_b, 'Cliente MC Obligaciones', 'J-80000805-5',
        )
        obligation_type = self.env['l10n.ve.obligation.type'].create({
            'name': 'Tipo MC 008C',
        })
        decoy = self.env['l10n.ve.obligation'].create({
            'name': 'Obligación Decoy A',
            'client_id': client_a.id,
            'obligation_type_id': obligation_type.id,
            'period': '07/2031',
        })

        wizard = self._create_wizard('obligation', self.company_b)
        self._map(wizard, 'name', 'char')
        self._map(wizard, 'client_id', 'many2one', 'l10n.ve.compliance.client')
        self._map(wizard, 'obligation_type_id', 'many2one', 'l10n.ve.obligation.type')
        self._map(wizard, 'period', 'char')
        line = self._line(wizard, {
            'name': 'Obligación MC',
            'client_id': 'Cliente MC Obligaciones',
            'obligation_type_id': 'Tipo MC 008C',
            'period': '07/2031',
        })

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(line.state, 'imported')
        obligations = self._search_as_admin_in_b('l10n.ve.obligation', [
            ('client_id', '=', client_b.id),
            ('obligation_type_id', '=', obligation_type.id),
            ('period', '=', '07/2031'),
        ])
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations.client_id, client_b)
        self.assertEqual(client_b.company_id, self.company_b)

        decoy_records = self.env['l10n.ve.obligation'].sudo().search([
            ('id', '=', decoy.id),
        ])
        self.assertEqual(len(decoy_records), 1)
        self.assertEqual(decoy_records.client_id, client_a)
        self.assertEqual(decoy_records.name, 'Obligación Decoy A')

    def test_import_document_non_active_company(self):
        """Importar documentos para el cliente de B sin tocar el decoy de A."""
        # El decoy de A se crea primero (id menor): sin el filtro de compañía
        # en `_resolve_values`, el search por nombre devolvería el de A.
        client_a = self._client(
            self.company_a, 'Cliente MC Obligaciones', 'J-80000807-7',
        )
        client_b = self._client(
            self.company_b, 'Cliente MC Obligaciones', 'J-80000805-5',
        )
        document_type = self.env['l10n.ve.document.type'].create({
            'name': 'Doc MC 008C',
            'code': 'MC008C',
        })
        decoy = self.env['l10n.ve.document'].create({
            'client_id': client_a.id,
            'document_type_id': document_type.id,
            'number': 'DOC-MC-001',
        })

        wizard = self._create_wizard('document', self.company_b)
        self._map(wizard, 'client_id', 'many2one', 'l10n.ve.compliance.client')
        self._map(wizard, 'document_type_id', 'many2one', 'l10n.ve.document.type')
        self._map(wizard, 'number', 'char')
        self._map(wizard, 'issue_date', 'date')
        self._map(wizard, 'expiry_date', 'date')
        line = self._line(wizard, {
            'client_id': 'Cliente MC Obligaciones',
            'document_type_id': 'Doc MC 008C',
            'number': 'DOC-MC-001',
            'issue_date': '2031-01-15',
            'expiry_date': '2032-01-15',
        })

        self._as_admin_in_a(wizard).action_import()
        line.invalidate_recordset(['state', 'error_msg'])

        self.assertEqual(line.state, 'imported')
        documents = self._search_as_admin_in_b('l10n.ve.document', [
            ('client_id', '=', client_b.id),
            ('document_type_id', '=', document_type.id),
            ('number', '=', 'DOC-MC-001'),
        ])
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents.client_id, client_b)

        decoy_records = self.env['l10n.ve.document'].sudo().search([
            ('id', '=', decoy.id),
        ])
        self.assertEqual(len(decoy_records), 1)
        self.assertEqual(decoy_records.client_id, client_a)

    def test_islr_load_non_active_company(self):
        """Cargar conciliación ISLR de B con A activa, sin mezclar homónimos."""
        client_b = self._client(
            self.company_b, 'Cliente ISLR MC B', 'J-99999999-0',
        )
        client_a = self._client(
            self.company_a, 'Cliente ISLR MC A', 'J-99999999-0',
        )
        Reconciliation = self.env['l10n.ve.islr.reconciliation']
        existing_b = Reconciliation.create({
            'client_id': client_b.id,
            'company_id': self.company_b.id,
            'fiscal_year': 2025,
        })
        existing_a = Reconciliation.create({
            'client_id': client_a.id,
            'company_id': self.company_a.id,
            'fiscal_year': 2025,
        })
        self.env['l10n.ve.islr.reconciliation.line'].create({
            'reconciliation_id': existing_a.id,
            'category': 'income',
            'code': 'ventas',
            'label': 'Rubro Decoy A 008C',
        })

        wizard = self._create_wizard('islr_conciliation', self.company_b)
        wizard.write({
            'file': base64.b64encode(FIXTURE_PATH.read_bytes()),
            'filename': 'conciliacion.xlsx',
        })

        self._as_admin_in_a(wizard).action_load_file()
        wizard.invalidate_recordset([
            'state',
            'conciliacion_client_id',
            'conciliacion_fiscal_year',
            'conciliacion_existing_id',
            'conciliacion_data',
        ])

        self.assertEqual(wizard.state, 'preview')
        self.assertEqual(wizard.conciliacion_client_id, client_b)
        self.assertEqual(wizard.conciliacion_fiscal_year, 2025)
        self.assertEqual(wizard.conciliacion_existing_id, existing_b)
        self.assertEqual(len(wizard.conciliacion_data['rubros']), 10)

        labels = [rubro['label'] for rubro in wizard.conciliacion_data['rubros']]
        self.assertNotIn('Rubro Decoy A 008C', labels)
        self.assertEqual(existing_a.line_ids.mapped('label'), ['Rubro Decoy A 008C'])

    def test_islr_import_creates_reconciliation_in_wizard_company(self):
        """Importar la conciliación ISLR en la compañía del wizard, no en A."""
        client_b = self._client(
            self.company_b, 'Cliente ISLR MC Import B', 'J-99999999-0',
        )
        client_a = self._client(
            self.company_a, 'Cliente ISLR MC Import A', 'J-99999999-0',
        )

        wizard = self._create_wizard('islr_conciliation', self.company_b)
        wizard.write({
            'file': base64.b64encode(FIXTURE_PATH.read_bytes()),
            'filename': 'conciliacion.xlsx',
        })

        self._as_admin_in_a(wizard).action_load_file()
        self._as_admin_in_a(wizard).action_import()
        wizard.invalidate_recordset(['state', 'conciliacion_existing_id'])

        self.assertEqual(wizard.state, 'done')
        Reconciliation = self.env['l10n.ve.islr.reconciliation']
        record = Reconciliation.sudo().search([
            ('client_id', '=', client_b.id),
            ('fiscal_year', '=', 2025),
        ])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.company_id, self.company_b)
        self.assertEqual(len(record.line_ids), 10)
        self.assertTrue(
            all(line.company_id == self.company_b for line in record.line_ids),
        )
        self.assertFalse(Reconciliation.sudo().search([
            ('client_id', '=', client_a.id),
        ]))
