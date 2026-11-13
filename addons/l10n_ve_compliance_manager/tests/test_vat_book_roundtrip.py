import base64
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVatBookRoundtrip(TransactionCase):
    """El XLSX exportado debe poder reimportarse sin perder datos fiscales."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Roundtrip, C.A.',
            'vat': 'J-99999999-9',
        })
        self.VatBookLine = self.env['l10n.ve.vat.book.line']
        self.ExportWizard = self.env['l10n.ve.vat.book.export.wizard']
        self.ImportWizard = self.env['l10n.ve.import.wizard']

    def _create_move(self, invoice_date, move_type='in_invoice'):
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Compras Roundtrip',
                'code': 'RTRP',
                'type': 'purchase',
                'company_id': self.company.id,
            })
        return self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': invoice_date,
            'journal_id': journal.id,
            'ref': 'CTRL-RT-001',
        })

    def _create_book_line(self):
        return self.VatBookLine.create({
            'book_type': 'purchase',
            'period_month': '2027-01',
            'partner_id': self.partner.id,
            'invoice_number': '001-001-00009999',
            'control_number': 'CTRL-RT-001',
            'operation_code': '31',
            'invoice_date': date(2027, 1, 15),
            'invoice_type': '01',
            'base_import_16': 1000.0,
            'vat_import_16': 160.0,
            'total_with_vat': 1160.0,
            'source': 'manual',
            'company_id': self.company.id,
        })

    def test_export_import_roundtrip_preserves_date_doc_type_and_import_base(self):
        """Exportar y reimportar conserva fecha, tipo doc y base de importación."""
        self._create_book_line()

        export = self.ExportWizard.create({
            'period_month': '2027-01',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        export.action_export_xlsx()
        xlsx = base64.b64decode(export.template_file)

        import_wizard = self.ImportWizard.create({
            'import_type': 'vat_book_purchase',
            'company_id': self.company.id,
            'period_month': '2027-01',
            'filename': 'roundtrip.xlsx',
            'file': base64.b64encode(xlsx),
        })
        import_wizard.action_load_file()
        self.assertEqual(len(import_wizard.line_ids), 1)
        import_wizard.action_import()

        import_line = import_wizard.line_ids[0]
        self.assertIn(import_line.state, ('imported', 'updated'), import_line.error_msg)

        imported = self.VatBookLine.search([
            ('period_month', '=', '2027-01'),
            ('partner_id', '=', self.partner.id),
            ('invoice_number', '=', '001-001-00009999'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported.invoice_date, date(2027, 1, 15))
        self.assertEqual(imported.invoice_type, '01')
        self.assertAlmostEqual(imported.base_import_16, 1000.0)
        self.assertAlmostEqual(imported.vat_import_16, 160.0)

    def test_prepare_book_line_vals_persists_move_date_and_type(self):
        """_prepare_book_line_vals copia fecha y tipo de documento del move."""
        move = self._create_move(date(2026, 11, 15))
        amounts = {
            'base_general': 1000.0,
            'vat_general': 160.0,
            'base_reduced': 0.0,
            'vat_reduced': 0.0,
            'base_no_credit': 0.0,
            'base_not_subject': 0.0,
            'base_not_taxed': 0.0,
        }
        vals = self.VatBookLine._prepare_book_line_vals(
            move, 16, amounts, 'to_vendor', '33'
        )
        self.assertEqual(vals['invoice_date'], date(2026, 11, 15))
        self.assertEqual(vals['invoice_type'], '01')

        refund = self._create_move(date(2026, 11, 20), move_type='in_refund')
        vals = self.VatBookLine._prepare_book_line_vals(
            refund, 16, amounts, 'to_vendor', '33'
        )
        self.assertEqual(vals['invoice_type'], '03')
