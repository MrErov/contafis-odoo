from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComplianceClient(TransactionCase):
    """Tests del modelo l10n.ve.compliance.client (kanban, logo, cartelera)."""

    def setUp(self):
        super().setUp()
        # Limpiar statuses de tests previos
        self.env['l10n.ve.cartelera.status'].search([]).unlink()
        self.Client = self.env['l10n.ve.compliance.client']
        self.DocType = self.env['l10n.ve.document.type']
        self.Status = self.env['l10n.ve.cartelera.status']
        self.Institution = self.env['l10n.ve.institution']

        # Cliente de prueba
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Test Kanban',
            'vat': 'J-12345678-9',
        })
        self.client = self.Client.create({
            'name': 'Cliente Test Kanban',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-12345678-9',
        })

        # Tipos de documento existentes en demo
        self.type_c01 = self.DocType.search([('code', '=', 'C01')], limit=1)

    def test_partner_image_related(self):
        """Verifica que partner_image_1920 es campo related sin columna propia."""
        field = self.Client._fields['partner_image_1920']
        # Es Binary
        self.assertEqual(field.type, 'binary')
        # Es related a partner_id.image_1920
        self.assertEqual(field.related, 'partner_id.image_1920')
        # NO tiene columna en BD (related no crea columna)
        self.assertFalse(field.store)

    def test_cartelera_html_render(self):
        """Verifica renderizado HTML de cartelera con escape XSS."""
        today = fields.Date.today()
        year = today.year
        month = str(today.month)

        # CASO 1: Sin statuses -> mensaje por defecto
        self.client.invalidate_recordset(['cartelera_html'])
        html = self.client.cartelera_html
        self.assertIn('Sin datos para el mes actual', html)

        # CASO 2: Con statuses validos -> contiene badges
        self.Status.create({
            'client_id': self.client.id,
            'document_type_id': self.type_c01.id,
            'year': year,
            'month': month,
            'state': 'valid',
        })
        self.client.invalidate_recordset(['cartelera_html'])
        html = self.client.cartelera_html
        self.assertIn('badge', html)
        self.assertIn('C01', html)

        # CASO 3: XSS - nombre institucion con <script>
        evil_inst = self.Institution.create({
            'name': '<script>alert(1)</script>',
            'type': 'otro',
        })
        evil_type = self.DocType.create({
            'name': 'Doc Evil',
            'code': 'EVL',
            'institution_id': evil_inst.id,
            'required_for': 'company',
        })
        self.Status.create({
            'client_id': self.client.id,
            'document_type_id': evil_type.id,
            'year': year,
            'month': month,
            'state': 'valid',
        })
        self.client.invalidate_recordset(['cartelera_html'])
        html = self.client.cartelera_html

        # Anti-patron: crudo NO debe estar
        self.assertNotIn('<script>', html)
        # Escapado SI debe estar
        self.assertIn('&lt;script&gt;', html)

    def test_cartelera_summary_counts(self):
        """Resume válidos/pendientes del mes actual para la tarjeta kanban."""
        today = fields.Date.today()
        doc_type_other = self.DocType.create({
            'name': 'Doc Summary',
            'code': 'SUM',
            'required_for': 'company',
        })
        self.Status.create([
            {
                'client_id': self.client.id,
                'document_type_id': self.type_c01.id,
                'year': today.year,
                'month': str(today.month),
                'state': 'valid',
            },
            {
                'client_id': self.client.id,
                'document_type_id': doc_type_other.id,
                'year': today.year,
                'month': str(today.month),
                'state': 'missing',
            },
        ])
        self.client.invalidate_recordset([
            'cartelera_valid_count',
            'cartelera_total_count',
            'cartelera_pending_count',
            'cartelera_progress',
        ])
        self.assertEqual(self.client.cartelera_total_count, 2)
        self.assertEqual(self.client.cartelera_valid_count, 1)
        self.assertEqual(self.client.cartelera_pending_count, 1)
        self.assertEqual(self.client.cartelera_progress, 50.0)
