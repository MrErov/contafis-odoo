from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install')
class TestIslrConciliacionModel(TransactionCase):
    """Tests del modelo base l10n.ve.islr.reconciliation (Spec 011 — T1)."""

    def setUp(self):
        super().setUp()
        self.env['l10n.ve.islr.reconciliation.line'].search([]).unlink()
        self.env['l10n.ve.islr.reconciliation'].search([]).unlink()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente ISLR Test',
            'vat': 'J-12345678-9',
        })
        self.client = self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente ISLR Test',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-12345678-9',
        })
        self.Reconciliacion = self.env['l10n.ve.islr.reconciliation']
        self.Line = self.env['l10n.ve.islr.reconciliation.line']

    def _create_reconciliation(self, **vals):
        base = {
            'client_id': self.client.id,
            'company_id': self.env.company.id,
            'fiscal_year': 2025,
        }
        base.update(vals)
        return self.Reconciliacion.create(base)

    def _create_line(self, reconciliation, **vals):
        base = {
            'reconciliation_id': reconciliation.id,
            'sequence': 10,
            'category': 'income',
            'code': 'ventas',
            'label': 'Ventas',
            'amount_accounting': 100.0,
            'amount_fiscal': 90.0,
            'amount_not_deductible': 10.0,
        }
        base.update(vals)
        return self.Line.create(base)

    def test_create_defaults(self):
        rec = self._create_reconciliation()
        self.assertEqual(rec.state, 'draft')
        self.assertEqual(rec.fiscal_year, 2025)
        self.assertEqual(rec.company_id, self.env.company)
        self.assertFalse(rec.line_ids)

    def test_name_incluye_rif_y_anio(self):
        rec = self._create_reconciliation()
        self.assertIn('J-12345678-9', rec.name)
        self.assertIn('2025', rec.name)

    def test_line_company_related_y_trazabilidad(self):
        rec = self._create_reconciliation()
        line = self._create_line(rec)
        self.assertEqual(line.company_id, self.env.company)
        self.assertFalse(line.modified_by)
        self.assertFalse(line.modified_at)
        line.write({'amount_fiscal': 95.0})
        self.assertEqual(line.modified_by, self.env.user)
        self.assertTrue(line.modified_at)

    def test_referencia_xlsx_y_adjunto(self):
        rec = self._create_reconciliation()
        self.assertFalse(rec.monto_a_pagar_xlsx)
        self.assertFalse(rec.pdf_attachment_id)
        rec.write({
            'totals_xlsx': {'monto_a_pagar': 47863.69},
            'monto_a_pagar_xlsx': 47863.69,
        })
        self.assertEqual(rec.monto_a_pagar_xlsx, 47863.69)
        self.assertEqual(rec.totals_xlsx['monto_a_pagar'], 47863.69)

    def test_trazabilidad_cabecera(self):
        rec = self._create_reconciliation()
        self.assertFalse(rec.modified_by)
        rec.write({'fiscal_year': 2025})
        self.assertEqual(rec.modified_by, self.env.user)
        self.assertTrue(rec.modified_at)

    def test_unique_cliente_compania_anio(self):
        self._create_reconciliation()
        with self.assertRaises(IntegrityError):
            self._create_reconciliation()
