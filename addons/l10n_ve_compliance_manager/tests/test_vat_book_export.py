from io import BytesIO

import openpyxl
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVatBookExport(TransactionCase):
    """Tests para exportación de Libro de Compras/Ventas a Excel (G.10)."""

    def setUp(self):
        super().setUp()
        # Limpiar datos de corridas previas
        self.env['l10n.ve.vat.book.line'].search([]).unlink()
        self.env['l10n.ve.vat.book.export.wizard'].search([]).unlink()

        self.Wizard = self.env['l10n.ve.vat.book.export.wizard']
        self.VatBookLine = self.env['l10n.ve.vat.book.line']
        self.partner = self.env['res.partner'].create({
            'name': 'Proveedor Test',
            'vat': 'J-31527189-4',
        })
        self.company = self.env.company

    def _create_vat_book_lines(self, book_type='purchase', count=3):
        """Crea líneas de vat.book.line para testing."""
        lines = []
        for i in range(count):
            if book_type == 'purchase':
                vals = {
                    'book_type': 'purchase',
                    'period_month': '2026-08',
                    'partner_id': self.partner.id,
                    'invoice_number': f'FAC-{i+1:03d}',
                    'control_number': f'CTRL-{i+1:03d}',
                    'operation_code': '33',
                    'base_general': 1000.0 * (i + 1),
                    'vat_general': 160.0 * (i + 1),
                    'base_reduced': 200.0 * (i + 1),
                    'vat_reduced': 16.0 * (i + 1),
                    'base_not_subject': 50.0 * (i + 1),
                    'base_no_credit': 30.0 * (i + 1),
                    'retention_number': f'RET-{i+1:03d}',
                    'vat_retained': 50.0 * (i + 1),
                    'retention_direction': 'to_vendor',
                    'company_id': self.company.id,
                }
            else:
                vals = {
                    'book_type': 'sale',
                    'period_month': '2026-08',
                    'partner_id': self.partner.id,
                    'invoice_number': f'FAC-SALE-{i+1:03d}',
                    'control_number': f'CTRL-SALE-{i+1:03d}',
                    'operation_code': '42',
                    'base_general': 1000.0 * (i + 1),
                    'vat_general': 160.0 * (i + 1),
                    'base_not_subject': 50.0 * (i + 1),
                    'base_not_taxed': 30.0 * (i + 1),
                    'retention_number': f'RET-SALE-{i+1:03d}',
                    'vat_retained': 50.0 * (i + 1),
                    'retention_direction': 'by_buyer',
                    'company_id': self.company.id,
                }
            lines.append(self.VatBookLine.create(vals))
        return lines

    def _read_xlsx(self, xlsx_bytes):
        """Lee un archivo XLSX y retorna workbook y hoja activa."""
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True)
        return wb, wb.active

    def test_export_purchase_generates_file(self):
        """Export compra genera archivo XLSX válido."""
        self._create_vat_book_lines('purchase', 3)

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        result = wizard.action_export_xlsx()

        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('Libro_Compras_2026-08.xlsx', result['url'])
        self.assertTrue(wizard.template_file)

        # Verificar contenido del XLSX
        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        # Verificar nombre de hoja
        self.assertEqual(ws.title, 'COMPRAS')

        # Verificar headers (fila 1)
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        expected_headers = [
            'R.I.F.',
            'Nombre o Razon Social',
            'Tipo Doc',
            'Numero de Factura',
            'Numero de Control',
            'Fecha',
            'Base Alicuota General 16%',
            'I.V.A. Alicuota General 16%',
            'Base Alicuota Reducida',
            'I.V.A. Alicuota Reducida',
            'Compras NO SUJETAS',
            'Compras sin Derecho a Credito (Nacional)',
            'Base Importación 16%',
            'I.V.A. de importación 16%',
            'Nº Comprob. Retención 75%',
            'IVA Retenido (al Vendedor)',
            'IVA Retenido (a Terceros)',
            'Anticipo IVA (Importación)',
        ]
        self.assertEqual(headers, expected_headers)

        # Verificar 3 filas de datos + 1 fila total = 5 filas total
        self.assertEqual(ws.max_row, 5)

        # Verificar fila TOTAL GENERAL (fila 5)
        total_row = 5
        self.assertEqual(ws.cell(row=total_row, column=1).value, 'TOTAL GENERAL')
        # Verificar que los totales son correctos
        # base_general: 1000 + 2000 + 3000 = 6000
        self.assertEqual(ws.cell(row=total_row, column=7).value, 6000.0)
        # vat_general: 160 + 320 + 480 = 960
        self.assertEqual(ws.cell(row=total_row, column=8).value, 960.0)
        # base_reduced: 200 + 400 + 600 = 1200
        self.assertEqual(ws.cell(row=total_row, column=9).value, 1200.0)
        # vat_reduced: 16 + 32 + 48 = 96
        self.assertEqual(ws.cell(row=total_row, column=10).value, 96.0)

    def test_export_sale_generates_file(self):
        """Export venta genera archivo XLSX válido."""
        self._create_vat_book_lines('sale', 2)

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'sale',
        })
        result = wizard.action_export_xlsx()

        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('Libro_Ventas_2026-08.xlsx', result['url'])
        self.assertTrue(wizard.template_file)

        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        self.assertEqual(ws.title, 'VENTAS')

        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        expected_headers = [
            'R.I.F.',
            'Nombre o Razon Social',
            'Tipo Doc',
            'Numero de Factura',
            'Numero de Control',
            'Fecha',
            'Ventas internas No sujetas',
            'Ventas internas no gravadas (No Contrib)',
            'Base Imponible (No Contrib)',
            'Impuesto IVA (No Contrib)',
            'Base Imponible (Contrib)',
            'Impuesto IVA (Contrib)',
            'Nº Comprob. Retención 75% IVA',
            'Iva Retenido (por comprador)',
        ]
        self.assertEqual(headers, expected_headers)

        # 2 filas datos + 1 total = 4 filas
        self.assertEqual(ws.max_row, 4)

        # Verificar total
        total_row = 4
        self.assertEqual(ws.cell(row=total_row, column=1).value, 'TOTAL GENERAL')
        # base_general (contrib): 1000 + 2000 = 3000
        self.assertEqual(ws.cell(row=total_row, column=11).value, 3000.0)
        # vat_general (contrib): 160 + 320 = 480
        self.assertEqual(ws.cell(row=total_row, column=12).value, 480.0)

    def test_export_both_generates_two_sheets(self):
        """Export both genera archivo con 2 hojas: COMPRAS y VENTAS."""
        self._create_vat_book_lines('purchase', 2)
        self._create_vat_book_lines('sale', 1)

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'both',
        })
        result = wizard.action_export_xlsx()

        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('Libro_Compras_Ventas_2026-08.xlsx', result['url'])
        self.assertTrue(wizard.template_file)

        xlsx = wizard.template_file.content
        wb = openpyxl.load_workbook(BytesIO(xlsx), data_only=True)

        # Verificar que tiene 2 hojas
        self.assertEqual(set(wb.sheetnames), {'COMPRAS', 'VENTAS'})

        # Verificar hoja COMPRAS
        ws_compras = wb['COMPRAS']
        self.assertEqual(ws_compras.max_row, 4)  # 3 datos + 1 total
        self.assertEqual(ws_compras.cell(row=4, column=1).value, 'TOTAL GENERAL')

        # Verificar hoja VENTAS
        ws_ventas = wb['VENTAS']
        self.assertEqual(ws_ventas.max_row, 3)  # header + 1 dato + 1 total
        self.assertEqual(ws_ventas.cell(row=3, column=1).value, 'TOTAL GENERAL')

    def test_export_empty_period_creates_headers_only(self):
        """Export período sin datos crea solo headers + total en 0."""
        wizard = self.Wizard.create({
            'period_month': '2026-09',  # Período sin datos
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()

        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        # Solo headers (fila 1) + total (fila 2) = 2 filas
        self.assertEqual(ws.max_row, 2)
        self.assertEqual(ws.cell(row=2, column=1).value, 'TOTAL GENERAL')
        # Todos los totales en 0
        for col in range(7, 18):  # Columnas numéricas
            self.assertEqual(ws.cell(row=2, column=col).value, 0.0)

    def test_export_headers_match_import_template(self):
        """Headers del export son idénticos al template de importación."""
        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        export_headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

        # Comparar con template de importación purchase
        import_wizard = self.env['l10n.ve.import.wizard'].create({
            'import_type': 'vat_book_purchase',
        })
        import_wizard.action_download_template()
        import_xlsx = import_wizard.template_file.content
        import_wb = openpyxl.load_workbook(BytesIO(import_xlsx))
        import_ws = import_wb.active
        import_headers = [import_ws.cell(row=1, column=c).value for c in range(1, import_ws.max_column + 1)]

        self.assertEqual(export_headers, import_headers)

    def test_export_sale_headers_match_import_template(self):
        """Headers del export venta son idénticos al template de importación."""
        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'sale',
        })
        wizard.action_export_xlsx()
        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        export_headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

        import_wizard = self.env['l10n.ve.import.wizard'].create({
            'import_type': 'vat_book_sale',
        })
        import_wizard.action_download_template()
        import_xlsx = import_wizard.template_file.content
        import_wb = openpyxl.load_workbook(BytesIO(import_xlsx))
        import_ws = import_wb.active
        import_headers = [import_ws.cell(row=1, column=c).value for c in range(1, import_ws.max_column + 1)]

        self.assertEqual(export_headers, import_headers)

    def test_export_action_open_wizard_from_line(self):
        """Botón 'Exportar' en línea abre wizard con período correcto."""
        line = self._create_vat_book_lines('purchase', 1)[0]

        action = line.action_open_export_wizard()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'l10n.ve.vat.book.export.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_period_month'], '2026-08')
        self.assertEqual(action['context']['default_company_id'], self.company.id)
        self.assertEqual(action['context']['default_book_type'], 'purchase')

    def test_export_retention_direction_split(self):
        """Export separa retenciones por dirección (to_vendor vs to_third)."""
        # Línea con retención to_vendor
        self.VatBookLine.create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'retention_number': 'RET-001',
            'vat_retained': 100.0,
            'retention_direction': 'to_vendor',
            'company_id': self.company.id,
        })
        # Línea con retención to_third (misma factura, distinto direction)
        self.VatBookLine.create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'retention_number': 'RET-001',
            'vat_retained': 50.0,
            'retention_direction': 'to_third',
            'company_id': self.company.id,
        })

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = wizard.template_file.content
        wb, ws = self._read_xlsx(xlsx)

        # Deben aparecer 2 filas de datos (constraint permite por distinto direction)
        self.assertEqual(ws.max_row, 4)  # header + 2 datos + total

        # Fila 2: to_third (orden alfabético: 'to_third' < 'to_vendor')
        self.assertEqual(ws.cell(row=2, column=16).value, 0.0)   # IVA Retenido (al Vendedor)
        self.assertEqual(ws.cell(row=2, column=17).value, 50.0)  # IVA Retenido (a Terceros)

        # Fila 3: to_vendor
        self.assertEqual(ws.cell(row=3, column=16).value, 100.0)  # IVA Retenido (al Vendedor)
        self.assertEqual(ws.cell(row=3, column=17).value, 0.0)   # IVA Retenido (a Terceros)

        # Total: 100 + 50 = 150 en to_vendor, 50 en to_third
        total_row = 4
        self.assertEqual(ws.cell(row=total_row, column=16).value, 100.0)
        self.assertEqual(ws.cell(row=total_row, column=17).value, 50.0)
