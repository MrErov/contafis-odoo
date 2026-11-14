import base64
from datetime import date
from io import BytesIO

from odoo import api, fields, models
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DATE_NUMBER_FORMAT = 'DD/MM/YYYY'
MONETARY_NUMBER_FORMAT = '#,##0.00'

# Columnas que no se suman en TOTAL GENERAL (texto o fecha).
NON_NUMERIC_HEADERS = frozenset({
    'R.I.F.',
    'Nombre o Razon Social',
    'Tipo Doc',
    'Numero de Factura',
    'Numero de Control',
    'Fecha',
    'Nº Comprob. Retención 75%',
    'Nº Comprob. Retención 75% IVA',
})

# Configuración de columnas: ancho y alineación por tipo.
# Claves coinciden con headers exactos de _get_export_headers.
COLUMN_CONFIG = {
    'R.I.F.': {'width': 16, 'align': 'center', 'type': 'text'},
    'Nombre o Razon Social': {'width': 35, 'align': 'left', 'type': 'text'},
    'Tipo Doc': {'width': 10, 'align': 'center', 'type': 'text'},
    'Numero de Factura': {'width': 18, 'align': 'center', 'type': 'text'},
    'Numero de Control': {'width': 18, 'align': 'center', 'type': 'text'},
    'Fecha': {'width': 12, 'align': 'center', 'type': 'date'},
    'Base Alicuota General 16%': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'I.V.A. Alicuota General 16%': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Base Alicuota Reducida': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'I.V.A. Alicuota Reducida': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Compras NO SUJETAS': {'width': 16, 'align': 'right', 'type': 'monetary'},
    'Compras sin Derecho a Credito (Nacional)': {'width': 16, 'align': 'right', 'type': 'monetary'},
    'Base Importación 16%': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'I.V.A. de importación 16%': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Nº Comprob. Retención 75%': {'width': 20, 'align': 'center', 'type': 'text'},
    'IVA Retenido (al Vendedor)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'IVA Retenido (a Terceros)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Anticipo IVA (Importación)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Total c/IVA': {'width': 16, 'align': 'right', 'type': 'monetary'},
    # Sale headers
    'Ventas internas No sujetas': {'width': 16, 'align': 'right', 'type': 'monetary'},
    'Ventas internas no gravadas (No Contrib)': {'width': 16, 'align': 'right', 'type': 'monetary'},
    'Base Imponible (No Contrib)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Impuesto IVA (No Contrib)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Base Imponible (Contrib)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Impuesto IVA (Contrib)': {'width': 18, 'align': 'right', 'type': 'monetary'},
    'Nº Comprob. Retención 75% IVA': {'width': 20, 'align': 'center', 'type': 'text'},
    'Iva Retenido (por comprador)': {'width': 18, 'align': 'right', 'type': 'monetary'},
}

# Colores del diseño
HEADER_BG_COLOR = '1F3864'      # Azul oscuro para headers
HEADER_FONT_COLOR = 'FFFFFF'    # Blanco para texto de headers
ZEBRA_LIGHT_COLOR = 'F2F2F2'    # Gris claro para filas pares
TOTAL_BG_COLOR = 'D9E1F2'       # Azul claro para fila de totales
TITLE_FONT_COLOR = '1F3864'     # Azul oscuro para título


class VatBookExportWizard(models.TransientModel):
    _name = 'l10n.ve.vat.book.export.wizard'
    _description = 'Wizard de Exportación Libro de Compras/Ventas a Excel'

    period_month = fields.Char(
        string='Período (YYYY-MM)',
        required=True,
        default=lambda self: self._get_default_period_month(),
        help='Formato: 2026-08',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    book_type = fields.Selection([
        ('purchase', 'Compras'),
        ('sale', 'Ventas'),
        ('both', 'Compras y Ventas'),
    ], string='Tipo de Libro', required=True, default='purchase')

    template_file = fields.Binary(string='Archivo Generado')
    filename = fields.Char(string='Nombre Archivo')

    def action_export_xlsx(self):
        """Genera y descarga el Excel según book_type."""
        self.ensure_one()
        self = self.with_company(self.company_id)

        if self.book_type == 'both':
            xlsx_content = self._generate_vat_book_both_xlsx()
            filename = f'Libro_Compras_Ventas_{self.period_month}.xlsx'
        elif self.book_type == 'purchase':
            xlsx_content = self._generate_vat_book_xlsx('purchase')
            filename = f'Libro_Compras_{self.period_month}.xlsx'
        else:
            xlsx_content = self._generate_vat_book_xlsx('sale')
            filename = f'Libro_Ventas_{self.period_month}.xlsx'

        self.write({
            'template_file': base64.b64encode(xlsx_content),
            'filename': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=l10n.ve.vat.book.export.wizard&id={self.id}'
                   f'&field=template_file&download=true&filename={filename}',
            'target': 'self',
        }

    @api.model
    def _get_default_period_month(self):
        """Período por defecto del wizard de export.

        Regla: el último período que tiene líneas para la compañía activa
        (y el tipo de libro pedido). Así, el contador que trabaja con datos
        de 2026-10 no exporta por error el mes actual vacío.
        Fallback: el mes en curso.
        """
        book_type = self.env.context.get('default_book_type') or self.book_type
        domain = [('company_id', '=', self.env.company.id)]
        if book_type in ('purchase', 'sale'):
            domain.append(('book_type', '=', book_type))
        line = self.env['l10n.ve.vat.book.line'].search(
            domain, order='period_month desc', limit=1
        )
        return line.period_month or fields.Date.context_today(self).strftime('%Y-%m')

    def _generate_vat_book_xlsx(self, book_type):
        """Genera Excel para un tipo de libro (purchase o sale)."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'COMPRAS' if book_type == 'purchase' else 'VENTAS'

        # Estilos
        header_font = Font(bold=True, color=HEADER_FONT_COLOR)
        header_fill = PatternFill(
            start_color=HEADER_BG_COLOR, end_color=HEADER_BG_COLOR, fill_type='solid'
        )
        header_align = Alignment(horizontal='center', wrap_text=True)
        title_font = Font(bold=True, size=14, color=TITLE_FONT_COLOR)
        subtitle_font = Font(size=11, color=TITLE_FONT_COLOR)
        total_font = Font(bold=True)
        total_fill = PatternFill(
            start_color=TOTAL_BG_COLOR, end_color=TOTAL_BG_COLOR, fill_type='solid'
        )
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )
        number_format = MONETARY_NUMBER_FORMAT

        self._write_sheet(ws, book_type, header_font, header_fill, header_align,
                         total_font, total_fill, thin_border, number_format, get_column_letter,
                         title_font, subtitle_font)

        # Guardar en bytes
        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    def _generate_vat_book_both_xlsx(self):
        """Genera Excel con 2 hojas: COMPRAS y VENTAS."""
        import openpyxl

        wb = openpyxl.Workbook()

        # Estilos comunes
        header_font = Font(bold=True, color=HEADER_FONT_COLOR)
        header_fill = PatternFill(
            start_color=HEADER_BG_COLOR, end_color=HEADER_BG_COLOR, fill_type='solid'
        )
        header_align = Alignment(horizontal='center', wrap_text=True)
        title_font = Font(bold=True, size=14, color=TITLE_FONT_COLOR)
        subtitle_font = Font(size=11, color=TITLE_FONT_COLOR)
        total_font = Font(bold=True)
        total_fill = PatternFill(
            start_color=TOTAL_BG_COLOR, end_color=TOTAL_BG_COLOR, fill_type='solid'
        )
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )
        number_format = MONETARY_NUMBER_FORMAT

        # Hoja COMPRAS
        ws_compras = wb.active
        ws_compras.title = 'COMPRAS'
        self._write_sheet(ws_compras, 'purchase', header_font, header_fill, header_align,
                         total_font, total_fill, thin_border, number_format, get_column_letter,
                         title_font, subtitle_font)

        # Hoja VENTAS
        ws_ventas = wb.create_sheet('VENTAS')
        self._write_sheet(ws_ventas, 'sale', header_font, header_fill, header_align,
                         total_font, total_fill, thin_border, number_format, get_column_letter,
                         title_font, subtitle_font)

        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    def _write_sheet(self, ws, book_type, header_font, header_fill, header_align,
                     total_font, total_fill, thin_border, number_format, get_column_letter,
                     title_font, subtitle_font):
        """Escribe una hoja completa con diseño visual mejorado.

        Layout:
        - Fila 1: Título (empresa, libro) - merge A:N
        - Fila 2: Subtítulo (RIF, período, moneda) - merge A:N
        - Fila 3: Vacía
        - Fila 4: Headers estilizados
        - Fila 5+: Datos con zebra striping
        - Fila N+1: Vacía (separador)
        - Fila N+2: Total general (merge A:F para label)
        """
        headers = self._get_export_headers(book_type)
        n_cols = len(headers)

        # ===== FILA 1: TÍTULO =====
        book_label = 'LIBRO DE COMPRAS' if book_type == 'purchase' else 'LIBRO DE VENTAS'
        if book_type == 'both':
            book_label = 'LIBRO DE COMPRAS Y VENTAS'
        title = f'{self.company_id.name or "Empresa"} — {book_label}'
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
        cell = ws.cell(row=1, column=1, value=title)
        cell.font = title_font
        cell.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[1].height = 30

        # ===== FILA 2: SUBTÍTULO =====
        rif = self.company_id.vat or 'R.I.F. no configurado'
        period = self.period_month
        currency = self.company_id.currency_id.name or 'VES'
        subtitle = f'R.I.F.: {rif}   |   Período: {period}   |   Moneda: {currency}'
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
        cell = ws.cell(row=2, column=1, value=subtitle)
        cell.font = subtitle_font
        cell.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[2].height = 22

        # ===== FILA 3: VACÍA =====
        ws.row_dimensions[3].height = 8

        # ===== FILA 4: HEADERS ESTILOSOS =====
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border
            # Ancho de columna desde config
            config = COLUMN_CONFIG.get(header, {'width': 16, 'align': 'center'})
            ws.column_dimensions[get_column_letter(col_idx)].width = config['width']
        ws.row_dimensions[4].height = 48

        # ===== FILAS 5+: DATOS CON ZEBRA STRIPING =====
        domain = [
            ('period_month', '=', self.period_month),
            ('company_id', '=', self.company_id.id),
            ('book_type', '=', book_type),
        ]
        lines = self.env['l10n.ve.vat.book.line'].search(domain, order='partner_id, invoice_number, operation_code, retention_direction')

        row_idx = 5
        totals = {
            header: 0.0
            for header in headers
            if header not in NON_NUMERIC_HEADERS
        }

        zebra_fill = PatternFill(start_color=ZEBRA_LIGHT_COLOR, end_color=ZEBRA_LIGHT_COLOR, fill_type='solid')
        center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        right_align = Alignment(horizontal='right', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')

        for line_idx, line in enumerate(lines):
            for col_idx, header in enumerate(headers, 1):
                value = self._get_cell_value(line, header, book_type)
                # `''` se serializa como `<c t="inlineStr"></c>` (sin `<is>`),
                # lo que hace que Excel marque el archivo como dañado.
                # Las celdas de texto vacías se omiten (equivalen a vacío).
                if isinstance(value, str) and not value:
                    value = None
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = thin_border

                # Formato según tipo de dato
                config = COLUMN_CONFIG.get(header, {'align': 'center', 'type': 'text'})
                if isinstance(value, date):
                    cell.number_format = DATE_NUMBER_FORMAT
                    cell.alignment = center_align
                elif isinstance(value, int | float):
                    cell.number_format = number_format
                    if config['align'] == 'right':
                        cell.alignment = right_align
                    elif config['align'] == 'center':
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align
                else:
                    cell.alignment = left_align if config['align'] == 'left' else center_align

                # Zebra striping en filas pares (line_idx 0-based -> row 5, 7, 9...)
                if line_idx % 2 == 1:
                    cell.fill = zebra_fill

                if isinstance(value, int | float):
                    totals[header] += value
            row_idx += 1

        # ===== FILA N+1: VACÍA (SEPARADOR) =====
        row_idx += 1

        # ===== FILA N+2: TOTAL GENERAL =====
        total_row = row_idx
        # Merge A:F para la etiqueta "TOTAL GENERAL"
        label_end_col = min(6, n_cols)  # Hasta columna F (6) o menos si hay menos columnas
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=label_end_col)
        cell = ws.cell(row=total_row, column=1, value='TOTAL GENERAL')
        cell.font = total_font
        cell.fill = total_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # Rellenar celdas mergeadas con el mismo estilo
        for c in range(2, label_end_col + 1):
            ccell = ws.cell(row=total_row, column=c)
            ccell.fill = total_fill
            ccell.border = thin_border

        # Columnas numéricas con totales
        for col_idx, header in enumerate(headers, 1):
            if col_idx <= label_end_col:
                continue  # Ya manejadas por el merge
            if header in totals:
                cell = ws.cell(row=total_row, column=col_idx, value=totals[header])
                cell.font = total_font
                cell.fill = total_fill
                cell.border = thin_border
                cell.number_format = number_format
                cell.alignment = right_align

        # ===== CONFIGURACIÓN DE HOJA =====
        # Freeze panes en A5 (fila de headers + 1)
        ws.freeze_panes = 'A5'
        # Auto filter desde fila 4
        ws.auto_filter.ref = f'A4:{get_column_letter(n_cols)}{4 + len(lines)}'
        # Ocultar gridlines
        ws.sheet_view.showGridLines = False

        # ===== CONFIGURACIÓN DE IMPRESIÓN =====
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins.left = 0.4
        ws.page_margins.right = 0.4
        ws.page_margins.top = 0.5
        ws.page_margins.bottom = 0.5
        ws.page_margins.header = 0.3
        ws.page_margins.footer = 0.3

    def _get_cell_value(self, line, header, book_type):
        """Obtiene el valor para una celda según el header y tipo de libro."""
        if book_type == 'purchase':
            return self._get_purchase_cell_value(line, header)
        else:
            return self._get_sale_cell_value(line, header)

    def _get_move_document_code(self, line):
        """Código SENIAT del tipo de documento (01 factura, 03 nota de crédito)."""
        if line.invoice_type:
            return line.invoice_type
        move = line.account_move_id
        if not move:
            return ''
        if move.move_type in ('in_invoice', 'out_invoice'):
            return '01'
        if move.move_type in ('in_refund', 'out_refund'):
            return '03'
        return ''

    def _get_move_date(self, line):
        """Fecha de emisión de la factura como objeto ``date`` nativo."""
        return line.invoice_date or (line.account_move_id.invoice_date or None)

    def _get_purchase_cell_value(self, line, header):
        """Valor para columnas de libro de compras."""
        if header == 'R.I.F.':
            return line.partner_id.vat or ''
        elif header == 'Nombre o Razon Social':
            return line.partner_id.name or ''
        elif header == 'Tipo Doc':
            return self._get_move_document_code(line)
        elif header == 'Numero de Factura':
            return line.invoice_number or ''
        elif header == 'Numero de Control':
            return line.control_number or ''
        elif header == 'Fecha':
            return self._get_move_date(line)
        elif header == 'Base Alicuota General 16%':
            return line.base_general or 0.0
        elif header == 'I.V.A. Alicuota General 16%':
            return line.vat_general or 0.0
        elif header == 'Base Alicuota Reducida':
            return line.base_reduced or 0.0
        elif header == 'I.V.A. Alicuota Reducida':
            return line.vat_reduced or 0.0
        elif header == 'Compras NO SUJETAS':
            return line.base_not_subject or 0.0
        elif header == 'Compras sin Derecho a Credito (Nacional)':
            return line.base_no_credit or 0.0
        elif header == 'Base Importación 16%':
            return line.base_import_16 or 0.0
        elif header == 'I.V.A. de importación 16%':
            return line.vat_import_16 or 0.0
        elif header == 'Nº Comprob. Retención 75%':
            return line.retention_number or ''
        elif header == 'IVA Retenido (al Vendedor)':
            if line.retention_direction == 'to_vendor':
                return line.vat_retained or 0.0
            return 0.0
        elif header == 'IVA Retenido (a Terceros)':
            if line.retention_direction == 'to_third':
                return line.vat_retained or 0.0
            return 0.0
        elif header == 'Anticipo IVA (Importación)':
            return line.anticipo_import or 0.0
        elif header == 'Total c/IVA':
            return line.total_with_vat or 0.0
        return 0.0

    def _get_sale_cell_value(self, line, header):
        """Valor para columnas de libro de ventas."""
        if header == 'R.I.F.':
            return line.partner_id.vat or ''
        elif header == 'Nombre o Razon Social':
            return line.partner_id.name or ''
        elif header == 'Tipo Doc':
            return self._get_move_document_code(line)
        elif header == 'Numero de Factura':
            return line.invoice_number or ''
        elif header == 'Numero de Control':
            return line.control_number or ''
        elif header == 'Fecha':
            return self._get_move_date(line)
        elif header == 'Ventas internas No sujetas':
            return line.base_not_subject or 0.0
        elif header == 'Ventas internas no gravadas (No Contrib)':
            return line.base_not_taxed or 0.0
        elif header == 'Base Imponible (No Contrib)':
            # Para ventas no contrib, la base general corresponde a operation_code 40/41
            if line.operation_code in ('40', '41'):
                return line.base_general or 0.0
            return 0.0
        elif header == 'Impuesto IVA (No Contrib)':
            if line.operation_code in ('40', '41'):
                return line.vat_general or 0.0
            return 0.0
        elif header == 'Base Imponible (Contrib)':
            # Para ventas contrib (gravadas 16%), operation_code 42/442/443
            if line.operation_code in ('42', '442', '443'):
                return line.base_general or 0.0
            return 0.0
        elif header == 'Impuesto IVA (Contrib)':
            if line.operation_code in ('42', '442', '443'):
                return line.vat_general or 0.0
            return 0.0
        elif header == 'Nº Comprob. Retención 75% IVA':
            return line.retention_number or ''
        elif header == 'Iva Retenido (por comprador)':
            if line.retention_direction == 'by_buyer':
                return line.vat_retained or 0.0
            return 0.0
        elif header == 'Total c/IVA':
            return line.total_with_vat or 0.0
        return 0.0

    def _get_export_headers(self, book_type):
        """Retorna los headers en el orden exacto del template de importación."""
        if book_type == 'purchase':
            return [
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
        else:
            return [
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
