import base64
from io import BytesIO

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyWizards(TransactionCase):
    """Aislamiento por compañía de los wizards de importación y planillas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía Wizards'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})

        # Partner compartido para test de importación (company_id = False)
        cls.partner_shared = cls.env['res.partner'].create({
            'name': 'Proveedor Compartido Wizards',
            'vat': 'J-99999999-9',
        })

        # Partner exclusivo de B
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Proveedor Exclusivo B',
            'vat': 'J-88888888-8',
            'company_id': cls.company_b.id,
        })

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

    def test_import_wizard_non_active_company(self):
        """Importar Libro IVA para Compañía B estando logueado en A."""
        Wizard = self.env['l10n.ve.import.wizard']
        wizard = Wizard.create({
            'import_type': 'vat_book_purchase',
            'period_month': '2031-02',
            'company_id': self.company_b.id,
            'mode': 'lax',
        })

        # Crear línea de import con datos completos
        ImportLine = self.env['l10n.ve.import.line']
        line = ImportLine.create({
            'wizard_id': wizard.id,
            'row_index': 1,
            'state': 'draft',
            'data': {
                'partner_vat': self.partner_b.vat,
                'partner_name': self.partner_b.name,
                'invoice_number': 'WIZ-IMP-B-001',
                'control_number': 'WIZ-CTRL-B-001',
                '_book_type': 'purchase',
                '_rate_type': 'general',
                'base_general': 1000.0,
                'vat_general': 160.0,
                'vat_retained_vendor': 0.0,
                'vat_retained_third': 0.0,
            },
        })

        # Ejecutar import como admin con A activa
        self._as_admin_in_a(wizard).action_import()

        # Invalidar cache de la línea
        line.invalidate_recordset(['state', 'error_msg'])

        # Verificar resultado
        self.assertIn(line.state, ('imported', 'updated'))
        self.assertFalse(line.error_msg)

        # Verificar que la línea de libro se creó en B
        book_lines = self._search_as_admin_in_b('l10n.ve.vat.book.line', [
            ('period_month', '=', '2031-02'),
            ('invoice_number', '=', 'WIZ-IMP-B-001'),
        ])
        self.assertEqual(len(book_lines), 1, "Debe existir exactamente 1 línea en B")
        bl = book_lines[0]
        self.assertEqual(bl.company_id, self.company_b)
        self.assertEqual(bl.base_general, 1000.0)
        self.assertEqual(bl.vat_general, 160.0)
        self.assertEqual(bl.book_type, 'purchase')

    def test_vat_return_non_active_company(self):
        """Cargar planilla IVA de B desde líneas de libro de B, con A activa."""
        VatReturn = self.env['l10n.ve.vat.return']

        # Return en B
        vat_return_b = VatReturn.create({
            'period_month': '2031-03',
            'company_id': self.company_b.id,
        })

        # Línea de libro REAL en B (operation_code 33 = base 16% compras)
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2031-03',
            'partner_id': self.partner_b.id,
            'invoice_number': 'WIZ-RET-B-001',
            'control_number': 'WIZ-CTRL-RET-B-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'company_id': self.company_b.id,
            'retention_direction': 'to_vendor',
        })

        # DECOY en A: misma operación y período, para probar que NO se cuela
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2031-03',
            'partner_id': self.partner_shared.id,
            'invoice_number': 'WIZ-RET-A-001',
            'control_number': 'WIZ-CTRL-RET-A-001',
            'operation_code': '33',
            'base_general': 777.0,
            'vat_general': 123.0,
            'company_id': self.company_a.id,
            'retention_direction': 'to_vendor',
        })

        # Ejecutar como admin con A activa
        self._as_admin_in_a(vat_return_b).action_load_from_book()

        vat_return_b.invalidate_recordset([
            'state', 'item_33', 'item_34', 'item_30', 'item_35', 'item_36'
        ])

        # Verificar
        self.assertEqual(vat_return_b.state, 'loaded')
        self.assertEqual(vat_return_b.item_33, 1000.0, "Debe ser solo la base de B (1000), no sumar decoy A (777)")
        self.assertEqual(vat_return_b.item_34, 160.0, "Debe ser solo el IVA de B (160)")
        self.assertEqual(vat_return_b.item_30, 0.0, "No debe haber compras sin crédito")
        self.assertEqual(vat_return_b.item_35, 1000.0, "Total bases debe ser solo B")
        self.assertEqual(vat_return_b.item_36, 160.0, "Total IVA compras debe ser solo B")

    def test_vat_book_export_non_active_company(self):
        """Exportar Libro IVA de B a Excel, con A activa."""
        # Crear línea de libro en B
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2031-04',
            'partner_id': self.partner_b.id,
            'invoice_number': 'WIZ-EXP-B-001',
            'control_number': 'WIZ-CTRL-EXP-B-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'company_id': self.company_b.id,
            'retention_direction': 'to_vendor',
        })

        # Wizard de export en B
        ExportWiz = self.env['l10n.ve.vat.book.export.wizard']
        wizard = ExportWiz.create({
            'company_id': self.company_b.id,
            'period_month': '2031-04',
            'book_type': 'purchase',
        })

        # Ejecutar export como admin con A activa
        self._as_admin_in_a(wizard).action_export_xlsx()
        wizard.invalidate_recordset(['template_file'])

        # Decodificar y abrir Excel
        xlsx_content = base64.b64decode(wizard.template_file)
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(xlsx_content))
        ws = wb['COMPRAS']

        # Debe haber: header (fila 1) + 1 dato (fila 2) + total (fila 3) = 3 filas
        self.assertEqual(ws.max_row, 3, "Excel debe tener header + 1 fila de datos + total")
        # Verificar que la fila 2 contiene nuestra factura
        invoice_cell = ws.cell(row=2, column=4)  # columna D = Numero de Factura
        self.assertEqual(invoice_cell.value, 'WIZ-EXP-B-001')
        # Verificar que NO es la fila de total
        self.assertNotEqual(ws.cell(row=2, column=1).value, 'TOTAL GENERAL')

    def test_vat_book_generate_reset_non_active_company(self):
        """Reset del wizard de generación borra líneas de B, con A activa."""
        GenWiz = self.env['l10n.ve.vat.book.generate']
        wizard = GenWiz.create({
            'period_month': '2031-05',
            'company_id': self.company_b.id,
            'book_type': 'both',
        })

        # Crear una línea de libro en B con wizard_id
        self.env['l10n.ve.vat.book.line'].create({
            'wizard_id': wizard.id,
            'book_type': 'purchase',
            'period_month': '2031-05',
            'partner_id': self.partner_b.id,
            'invoice_number': 'WIZ-GEN-B-001',
            'control_number': 'WIZ-CTRL-GEN-B-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'company_id': self.company_b.id,
            'retention_direction': 'to_vendor',
        })

        # Ejecutar reset como admin con A activa
        self._as_admin_in_a(wizard).action_reset()
        wizard.invalidate_recordset(['state', 'move_ids'])

        # Verificar con sudo (sin regla) que la línea se borró
        remaining = self.env['l10n.ve.vat.book.line'].sudo().search([
            ('wizard_id', '=', wizard.id),
        ])
        self.assertEqual(len(remaining), 0, "action_reset debe borrar líneas de B aunque A esté activa")
        self.assertEqual(wizard.state, 'draft')
        self.assertEqual(len(wizard.move_ids), 0)
