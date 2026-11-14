import base64
import zipfile
from datetime import date, datetime
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

    def _read_sheet_xml(self, xlsx_bytes):
        """Retorna el XML crudo de la hoja activa (para checks de integridad)."""
        with zipfile.ZipFile(BytesIO(xlsx_bytes)) as zf:
            return zf.read('xl/worksheets/sheet1.xml').decode('utf-8')

    def _get_data_sheet_info(self, ws):
        """Helper para obtener info de la hoja con el nuevo layout."""
        # En el nuevo diseño:
        # Fila 1: Título (merge)
        # Fila 2: Subtítulo (merge)
        # Fila 3: Vacía
        # Fila 4: Headers
        # Fila 5+: Datos
        return {
            'header_row': 4,
            'data_start_row': 5,
        }

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
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        # Verificar nombre de hoja
        self.assertEqual(ws.title, 'COMPRAS')

        # Verificar título en fila 1
        self.assertIn('LIBRO DE COMPRAS', ws.cell(row=1, column=1).value)

        # Verificar subtítulo en fila 2
        subtitle = ws.cell(row=2, column=1).value
        self.assertIn('R.I.F.:', subtitle)
        self.assertIn('Período: 2026-08', subtitle)
        self.assertIn('Moneda:', subtitle)

        # Verificar headers en fila 4
        headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]
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
            'Total c/IVA',
        ]
        self.assertEqual(headers, expected_headers)

        # Verificar freeze_panes en A5
        self.assertEqual(ws.freeze_panes, 'A5')

        # Verificar auto_filter
        self.assertIsNotNone(ws.auto_filter.ref)

        # Verificar que gridlines están ocultas
        self.assertFalse(ws.sheet_view.showGridLines)

        # Verificar configuración de impresión
        self.assertEqual(ws.page_setup.orientation, 'landscape')
        self.assertEqual(ws.page_setup.fitToWidth, 1)

        # Verificar 3 filas de datos (fila 5, 6, 7) + 1 vacía (8) + 1 total (9) = 9 filas
        self.assertEqual(ws.max_row, 9)

        # Verificar fila TOTAL GENERAL (fila 9)
        total_row = 9
        # TOTAL GENERAL está mergeado en A:F
        self.assertEqual(ws.cell(row=total_row, column=1).value, 'TOTAL GENERAL')
        # Verificar que los totales son correctos
        # base_general: 1000 + 2000 + 3000 = 6000 (columna 7)
        self.assertEqual(ws.cell(row=total_row, column=7).value, 6000.0)
        # vat_general: 160 + 320 + 480 = 960 (columna 8)
        self.assertEqual(ws.cell(row=total_row, column=8).value, 960.0)
        # base_reduced: 200 + 400 + 600 = 1200 (columna 9)
        self.assertEqual(ws.cell(row=total_row, column=9).value, 1200.0)
        # vat_reduced: 16 + 32 + 48 = 96 (columna 10)
        self.assertEqual(ws.cell(row=total_row, column=10).value, 96.0)

    def test_export_total_row_leaves_text_columns_empty(self):
        """TOTAL GENERAL no debe escribir 0.00 en columnas de texto."""
        self._create_vat_book_lines('purchase', 2)

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        total_row = ws.max_row
        self.assertEqual(ws.cell(row=total_row, column=1).value, 'TOTAL GENERAL')
        # Columnas de texto: 2 (Nombre), 3 (Tipo Doc), 4 (Num Factura), 5 (Num Control), 6 (Fecha), 15 (Nº Comprob Ret)
        for col in (2, 3, 4, 5, 6, 15):
            self.assertIsNone(
                ws.cell(row=total_row, column=col).value,
                f'La columna {col} es de texto y no debe tener total',
            )
        self.assertEqual(ws.cell(row=total_row, column=7).value, 3000.0)
        self.assertEqual(ws.cell(row=total_row, column=8).value, 480.0)

    def test_export_fills_seniat_date_doc_type_and_total(self):
        """El XLSX incluye fecha, tipo de documento y total c/IVA."""
        account = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company.id]),
        ], limit=1)
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Compras Export Test',
                'code': 'EXPX',
                'type': 'purchase',
                'company_id': self.company.id,
                'default_account_id': account.id if account else False,
            })
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-20',
            'journal_id': journal.id,
        })
        self.VatBookLine.create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': '001-001-00001234',
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 100.0,
            'vat_general': 16.0,
            'total_with_vat': 116.0,
            'account_move_id': move.id,
            'source': 'odoo_invoice',
            'company_id': self.company.id,
        })

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]
        total_col = headers.index('Total c/IVA') + 1

        # Datos en fila 5 (data_start_row = 5)
        self.assertEqual(ws.cell(row=5, column=3).value, '01')
        date_value = ws.cell(row=5, column=6).value
        self.assertIsInstance(date_value, (date, datetime))
        if isinstance(date_value, datetime):
            date_value = date_value.date()
        self.assertEqual(date_value, date(2026, 8, 20))
        self.assertEqual(ws.cell(row=5, column=6).number_format, 'DD/MM/YYYY')
        self.assertEqual(ws.cell(row=5, column=total_col).value, 116.0)
        # Fila TOTAL GENERAL (fila 7 = 5 data + 1 empty + 1 total)
        self.assertEqual(ws.cell(row=7, column=total_col).value, 116.0)

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

        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        self.assertEqual(ws.title, 'VENTAS')

        # Verificar título y subtítulo
        self.assertIn('LIBRO DE VENTAS', ws.cell(row=1, column=1).value)

        # Verificar headers en fila 4
        headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]
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
            'Total c/IVA',
        ]
        self.assertEqual(headers, expected_headers)

        # Verificar freeze_panes y auto_filter
        self.assertEqual(ws.freeze_panes, 'A5')
        self.assertIsNotNone(ws.auto_filter.ref)
        self.assertFalse(ws.sheet_view.showGridLines)

        # 2 filas datos (5, 6) + 1 vacía (7) + 1 total (8) = 8 filas
        self.assertEqual(ws.max_row, 8)

        # Verificar total
        total_row = 8
        self.assertEqual(ws.cell(row=total_row, column=1).value, 'TOTAL GENERAL')
        # base_general (contrib): 1000 + 2000 = 3000 (columna 11)
        self.assertEqual(ws.cell(row=total_row, column=11).value, 3000.0)
        # vat_general (contrib): 160 + 320 = 480 (columna 12)
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

        xlsx = base64.b64decode(wizard.template_file)
        wb = openpyxl.load_workbook(BytesIO(xlsx), data_only=True)

        # Verificar que tiene 2 hojas
        self.assertEqual(set(wb.sheetnames), {'COMPRAS', 'VENTAS'})

        # Verificar hoja COMPRAS
        ws_compras = wb['COMPRAS']
        # 2 filas datos (5, 6) + 1 vacía (7) + 1 total (8) = 8 filas
        self.assertEqual(ws_compras.max_row, 8)
        self.assertEqual(ws_compras.cell(row=8, column=1).value, 'TOTAL GENERAL')

        # Verificar hoja VENTAS
        ws_ventas = wb['VENTAS']
        # 1 fila datos (5) + 1 vacía (6) + 1 total (7) = 7 filas
        self.assertEqual(ws_ventas.max_row, 7)
        self.assertEqual(ws_ventas.cell(row=7, column=1).value, 'TOTAL GENERAL')

    def test_export_empty_period_creates_headers_only(self):
        """Export período sin datos crea solo headers + total en 0."""
        wizard = self.Wizard.create({
            'period_month': '2026-09',  # Período sin datos
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()

        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        # Título (1) + Subtítulo (2) + Vacía (3) + Headers (4) + Vacía (5) + Total (6) = 6 filas
        self.assertEqual(ws.max_row, 6)
        self.assertEqual(ws.cell(row=6, column=1).value, 'TOTAL GENERAL')
        # Columnas numéricas en 0; las de texto quedan vacías
        numeric_cols = {7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19}
        text_cols = {2, 3, 4, 5, 6, 15}
        total_row = 6
        for col in numeric_cols:
            self.assertEqual(ws.cell(row=total_row, column=col).value, 0.0)
        for col in text_cols:
            self.assertIsNone(ws.cell(row=total_row, column=col).value)

    def test_export_headers_match_import_template(self):
        """Headers del export son idénticos al template de importación."""
        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        export_headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]

        # Comparar con template de importación purchase
        import_wizard = self.env['l10n.ve.import.wizard'].create({
            'import_type': 'vat_book_purchase',
        })
        import_wizard.action_download_template()
        import_xlsx = base64.b64decode(import_wizard.template_file)
        import_wb = openpyxl.load_workbook(BytesIO(import_xlsx))
        import_ws = import_wb.active
        import_headers = [import_ws.cell(row=1, column=c).value for c in range(1, import_ws.max_column + 1)]

        self.assertEqual(export_headers, import_headers + ['Total c/IVA'])

    def test_export_sale_headers_match_import_template(self):
        """Headers del export venta son idénticos al template de importación."""
        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'sale',
        })
        wizard.action_export_xlsx()
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        export_headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]

        import_wizard = self.env['l10n.ve.import.wizard'].create({
            'import_type': 'vat_book_sale',
        })
        import_wizard.action_download_template()
        import_xlsx = base64.b64decode(import_wizard.template_file)
        import_wb = openpyxl.load_workbook(BytesIO(import_xlsx))
        import_ws = import_wb.active
        import_headers = [import_ws.cell(row=1, column=c).value for c in range(1, import_ws.max_column + 1)]

        self.assertEqual(export_headers, import_headers + ['Total c/IVA'])

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
        xlsx = base64.b64decode(wizard.template_file)
        wb, ws = self._read_xlsx(xlsx)

        # Deben aparecer 2 filas de datos (constraint permite por distinto direction)
        # 2 filas datos (5, 6) + 1 vacía (7) + 1 total (8) = 8 filas
        self.assertEqual(ws.max_row, 8)

        # Fila 5: to_third (orden alfabético: 'to_third' < 'to_vendor')
        self.assertEqual(ws.cell(row=5, column=16).value, 0.0)   # IVA Retenido (al Vendedor)
        self.assertEqual(ws.cell(row=5, column=17).value, 50.0)  # IVA Retenido (a Terceros)

        # Fila 6: to_vendor
        self.assertEqual(ws.cell(row=6, column=16).value, 100.0)  # IVA Retenido (al Vendedor)
        self.assertEqual(ws.cell(row=6, column=17).value, 0.0)   # IVA Retenido (a Terceros)

        # Total: 100 + 50 = 150 en to_vendor, 50 en to_third (fila 8)
        total_row = 8
        self.assertEqual(ws.cell(row=total_row, column=16).value, 100.0)
        self.assertEqual(ws.cell(row=total_row, column=17).value, 50.0)

    def test_export_does_not_write_empty_string_cells(self):
        """Texto vacío NO debe escribirse en el XLSX.

        openpyxl serializa `''` como `<c t="inlineStr"></c>` (sin el elemento
        `<is>` que exige el formato). Excel marca ese archivo como dañado y
        pide "repararlo" al abrirlo. Las celdas vacías deben omitirse.
        """
        self.VatBookLine.create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-SINDATOS-001',
            'operation_code': '33',
            'base_general': 100.0,
            'vat_general': 16.0,
            'company_id': self.company.id,
        })

        wizard = self.Wizard.create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'book_type': 'purchase',
        })
        wizard.action_export_xlsx()
        xlsx = base64.b64decode(wizard.template_file)

        # 1) Las celdas de texto vacías se leen como None (celda inexistente)
        wb, ws = self._read_xlsx(xlsx)
        self.assertEqual(ws.cell(row=5, column=4).value, 'FAC-SINDATOS-001')  # Factura sí tiene dato
        self.assertIsNone(ws.cell(row=5, column=5).value)   # Nº de Control vacío
        self.assertIsNone(ws.cell(row=5, column=3).value)   # Tipo Doc vacío (sin move)
        self.assertIsNone(ws.cell(row=5, column=15).value)  # Nº Comprob. Retención vacío

        # 2) El XML no debe contener celdas inlineStr vacías
        sheet_xml = self._read_sheet_xml(xlsx)
        self.assertNotIn('t="inlineStr"></c>', sheet_xml)
        self.assertNotIn("t='inlineStr'></c>", sheet_xml)

    def test_export_wizard_default_period_is_latest_month_with_data(self):
        """El wizard debe abrir en el último período con datos, no en el mes actual.

        Escenario real: el contador tiene datos de 2026-10 y ejecuta el export
        en noviembre; si el período por defecto es "hoy", el archivo sale vacío.
        """
        self._create_vat_book_lines('purchase', 1)  # período 2026-08

        wizard = self.Wizard.with_context(default_book_type='purchase').create({})

        self.assertEqual(wizard.period_month, '2026-08')
