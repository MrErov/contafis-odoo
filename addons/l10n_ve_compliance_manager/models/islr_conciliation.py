import re
import unicodedata
from io import BytesIO

import openpyxl
from markupsafe import Markup, escape
from odoo import api, fields, models

TOTAL_TAX_RATE = 0.34

SIDE_LABELS = {
    'accounting': 'contabilidad',
    'fiscal': 'fiscal',
}

WARNING_TOTAL_LABELS = {
    'total_ingresos': 'Total ingresos',
    'mercancia_disponible': 'Mercancía disponible',
    'total_costo_venta': 'Total costo de venta',
    'renta_bruta': 'Renta bruta',
    'total_deducciones': 'Total deducciones',
    'utilidad_neta': 'Utilidad neta',
}

TOTAL_FIELDS = {
    'total_ingresos': ('total_ingresos_accounting', 'total_ingresos_fiscal'),
    'mercancia_disponible': ('mercancia_disponible_accounting', 'mercancia_disponible_fiscal'),
    'total_costo_venta': ('total_costo_venta_accounting', 'total_costo_venta_fiscal'),
    'renta_bruta': ('renta_bruta_accounting', 'renta_bruta_fiscal'),
    'total_deducciones': ('total_deducciones_accounting', 'total_deducciones_fiscal'),
    'utilidad_neta': ('utilidad_neta_accounting', 'utilidad_neta_fiscal'),
}


class IslrParseError(Exception):
    """Error de parseo de la conciliación ISLR (el wizard lo convierte en UserError)."""


RIF_RE = re.compile(r'([VEJPGvejpg])[-.\s]?(\d{7,9})[-.\s]?(\d)')
YEAR_RE = re.compile(r'(\d{4})')

SECTION_MAP = {
    'ingresos': 'income',
    'costos de venta': 'cost',
    'deducciones': 'deduction',
}

TOTALS_PREFIX = (
    ('total ingresos', 'total_ingresos'),
    ('total costo', 'total_costo_venta'),
    ('total deducciones', 'total_deducciones'),
    ('utilidad neta', 'utilidad_neta'),
)

TOTALS_EXACT = {
    'mercancia disponible': 'mercancia_disponible',
    'renta bruta': 'renta_bruta',
}

RUBRO_MAP = {
    'ventas': ('ventas', 'income'),
    'inventario inicial de mercancia': ('inventario_inicial', 'cost'),
    'compras de mercancias': ('compras_mercancia', 'cost'),
    'inventario final': ('inventario_final', 'cost'),
    'sueldos directivos': ('sueldos_directivos', 'deduction'),
    'sueldos y salarios del personal directivo y gerencial': ('sueldos_directivos', 'deduction'),
    'tributos pagados al semat': ('tributos_pagados', 'deduction'),
    'tributos pagados al seniat': ('tributos_pagados', 'deduction'),
    'arrendamientos bienes inmuebles': ('arrendamientos', 'deduction'),
    'arrendamentos bienes inmuebles': ('arrendamientos', 'deduction'),
    'arrendamientos': ('arrendamientos', 'deduction'),
    'otros gastos': ('otros_gastos', 'deduction'),
    'gastos representacion': ('gastos_representacion', 'deduction'),
    'gastos generales': ('gastos_generales', 'deduction'),
    'gastos generales(trabajo realizados por contrato': ('gastos_generales', 'deduction'),
    'gastos de transporte': ('gastos_transporte', 'deduction'),
    'gastos de trabajo realizados segun ley de trabajo': ('gastos_trabajo', 'deduction'),
    'gastos de reparaciones ordinarias': ('gastos_reparaciones', 'deduction'),
    'servicios de internet': ('servicios_internet', 'deduction'),
    'gastos de depreciacion': ('gastos_depreciacion', 'deduction'),
}


def sanitize_rif(value):
    """Normaliza un RIF para comparar: mayúsculas sin guiones, puntos ni espacios."""
    if not value:
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(value)).upper()


def normalize_label(value):
    """Normaliza etiquetas: minúsculas, sin acentos, sin espacios de más."""
    if not value:
        return ''
    text = unicodedata.normalize('NFKD', str(value))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return ' '.join(text.casefold().split())


def to_amount(value):
    """Convierte una celda a importe. Retorna (importe, había_texto)."""
    if value is None:
        return 0.0, False
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value), False
    text = str(value).strip()
    if not text:
        return 0.0, False
    try:
        return float(text), False
    except ValueError:
        return 0.0, True


def parse_conciliacion_xlsx(file_bytes):
    """Parsea la hoja 'Conciliación Fiscal' de un Excel y retorna un dict.

    Lee solo el bloque principal (filas 13-46, columnas B-F): rubros con sus
    tres columnas de importes, totales de referencia, monto a pagar informado,
    celdas con texto en columnas numéricas y etiquetas duplicadas.
    """
    try:
        workbook = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    except Exception as error:
        raise IslrParseError(f'No se pudo abrir el archivo Excel: {error}') from error

    sheet = None
    for candidate in workbook.worksheets:
        if normalize_label(candidate.title) == normalize_label('Conciliación Fiscal'):
            sheet = candidate
            break
    if sheet is None:
        raise IslrParseError('No se encontró la hoja "Conciliación Fiscal" en el archivo.')

    fiscal_year = None
    for row in range(1, 13):
        for column in 'ABCDEF':
            value = sheet[f'{column}{row}'].value
            if isinstance(value, str) and 'periodo fiscal' in normalize_label(value):
                years = YEAR_RE.findall(value)
                if years:
                    fiscal_year = int(years[-1])
        if fiscal_year:
            break
    if not fiscal_year:
        raise IslrParseError('No se pudo determinar el período fiscal en la hoja "Conciliación Fiscal".')

    rif = None
    for row in range(1, 13):
        for column in 'ABCDEF':
            value = sheet[f'{column}{row}'].value
            if isinstance(value, str):
                match = RIF_RE.search(value)
                if match:
                    rif = match.group(0)
                    break
        if rif:
            break
    if not rif:
        raise IslrParseError('No se pudo determinar el RIF en la hoja "Conciliación Fiscal".')

    rubros = []
    totals = {}
    monto_a_pagar = 0.0
    text_cells = []
    section = None

    for row in range(13, 47):
        label_monto = sheet[f'E{row}'].value
        if isinstance(label_monto, str) and 'monto a pagar' in normalize_label(label_monto):
            monto, had_text = to_amount(sheet[f'F{row}'].value)
            if had_text:
                text_cells.append(f'F{row}')
            monto_a_pagar = monto
            continue

        label = sheet[f'B{row}'].value
        if label is None or not str(label).strip():
            continue
        normalized = normalize_label(label)

        if normalized in SECTION_MAP:
            section = SECTION_MAP[normalized]
            continue

        totals_key = next(
            (key for prefix, key in TOTALS_PREFIX if normalized.startswith(prefix)),
            None,
        )
        if totals_key is None:
            totals_key = TOTALS_EXACT.get(normalized)
        if totals_key:
            accounting, had_text = to_amount(sheet[f'C{row}'].value)
            if had_text:
                text_cells.append(f'C{row}')
            fiscal, had_text = to_amount(sheet[f'D{row}'].value)
            if had_text:
                text_cells.append(f'D{row}')
            totals[totals_key] = {'accounting': accounting, 'fiscal': fiscal}
            continue

        raw_c = sheet[f'C{row}'].value
        raw_d = sheet[f'D{row}'].value
        raw_e = sheet[f'E{row}'].value
        raw_f = sheet[f'F{row}'].value
        if raw_c is None and raw_d is None and raw_e is None and raw_f is None:
            continue

        accounting, had_text = to_amount(raw_c)
        if had_text:
            text_cells.append(f'C{row}')
        fiscal, had_text = to_amount(raw_d)
        if had_text:
            text_cells.append(f'D{row}')
        not_deductible, had_text = to_amount(raw_e)
        if had_text:
            text_cells.append(f'E{row}')

        code, category = RUBRO_MAP.get(normalized, ('otro', section or 'deduction'))
        rubros.append({
            'sequence': row,
            'label': str(label).strip(),
            'code': code,
            'category': category,
            'accounting': accounting,
            'fiscal': fiscal,
            'not_deductible': not_deductible,
            'legal_basis': str(raw_f).strip() if raw_f is not None else False,
        })

    merged = {}
    duplicates = []
    for rubro in rubros:
        key = normalize_label(rubro['label'])
        if key in merged:
            target = merged[key]
            target['accounting'] += rubro['accounting']
            target['fiscal'] += rubro['fiscal']
            target['not_deductible'] += rubro['not_deductible']
            if key not in duplicates:
                duplicates.append(key)
        else:
            merged[key] = rubro

    return {
        'fiscal_year': fiscal_year,
        'rif': rif,
        'rubros': list(merged.values()),
        'totals': totals,
        'monto_a_pagar_xlsx': monto_a_pagar,
        'text_cells': text_cells,
        'duplicates': duplicates,
    }


class IslrReconciliation(models.Model):
    _name = 'l10n.ve.islr.reconciliation'
    _description = 'Conciliación Fiscal ISLR'
    _order = 'fiscal_year desc, client_id'

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
    )

    client_id = fields.Many2one(
        'l10n.ve.compliance.client',
        string='Cliente',
        required=True,
        ondelete='cascade',
        index=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    fiscal_year = fields.Integer(
        string='Año Fiscal',
        required=True,
        index=True,
        help='Año del período fiscal (ej: 2025)',
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validada'),
    ], string='Estado', default='draft', readonly=True)

    totals_xlsx = fields.Json(
        string='Totales de Referencia (Excel)',
        help='Totales informados en el Excel; referencia para las advertencias.',
    )

    monto_a_pagar_xlsx = fields.Float(
        string='Monto a Pagar informado (Excel)',
        digits='Account',
    )

    pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='PDF Generado',
        readonly=True,
        ondelete='set null',
    )

    line_ids = fields.One2many(
        'l10n.ve.islr.reconciliation.line',
        'reconciliation_id',
        string='Rubros',
    )

    total_ingresos_accounting = fields.Float(
        string='Total Ingresos (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    total_ingresos_fiscal = fields.Float(
        string='Total Ingresos (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    mercancia_disponible_accounting = fields.Float(
        string='Mercancía Disponible (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    mercancia_disponible_fiscal = fields.Float(
        string='Mercancía Disponible (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    total_costo_venta_accounting = fields.Float(
        string='Total Costo de Venta (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    total_costo_venta_fiscal = fields.Float(
        string='Total Costo de Venta (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    renta_bruta_accounting = fields.Float(
        string='Renta Bruta (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    renta_bruta_fiscal = fields.Float(
        string='Renta Bruta (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    total_deducciones_accounting = fields.Float(
        string='Total Deducciones (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    total_deducciones_fiscal = fields.Float(
        string='Total Deducciones (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    utilidad_neta_accounting = fields.Float(
        string='Utilidad Neta (Contabilidad)',
        compute='_compute_totals', store=True, digits='Account',
    )
    utilidad_neta_fiscal = fields.Float(
        string='Utilidad Neta (Fiscal)',
        compute='_compute_totals', store=True, digits='Account',
    )
    monto_a_pagar_calculado = fields.Float(
        string='Monto a Pagar Calculado',
        compute='_compute_totals', store=True, digits='Account',
        help='Utilidad neta fiscal multiplicada por la tarifa del 34% '
             '(personas jurídicas, Art. 52 LISLR).',
    )

    import_meta = fields.Json(
        string='Metadatos de Importación',
        help='Rubros duplicados y celdas con texto detectados al importar '
             '(alimentan las advertencias).',
    )

    source_file = fields.Char(
        string='Archivo Fuente',
        compute='_compute_import_trace',
    )

    imported_by = fields.Char(
        string='Importado por',
        compute='_compute_import_trace',
    )

    imported_at = fields.Datetime(
        string='Importado en',
        compute='_compute_import_trace',
    )

    warning_html = fields.Html(
        string='Advertencias',
        compute='_compute_warning_html',
        store=True,
        sanitize=False,
    )

    modified_by = fields.Many2one(
        'res.users',
        string='Modificado por',
    )

    modified_at = fields.Datetime(
        string='Modificado en',
        readonly=True,
    )

    @api.depends('client_id.name', 'client_id.rif', 'fiscal_year')
    def _compute_name(self):
        for record in self:
            identificacion = record.client_id.rif or record.client_id.name or ''
            anio = record.fiscal_year or ''
            record.name = f'{identificacion} - {anio}'.strip(' -')

    @api.depends(
        'line_ids.category',
        'line_ids.code',
        'line_ids.amount_accounting',
        'line_ids.amount_fiscal',
    )
    def _compute_totals(self):
        for record in self:
            lines = record.line_ids
            income = lines.filtered(lambda line: line.category == 'income')
            inv_inicial = lines.filtered(lambda line: line.code == 'inventario_inicial')
            compras = lines.filtered(lambda line: line.code == 'compras_mercancia')
            inv_final = lines.filtered(lambda line: line.code == 'inventario_final')
            deductions = lines.filtered(lambda line: line.category == 'deduction')
            for suffix in ('accounting', 'fiscal'):
                amount_field = f'amount_{suffix}'
                ingresos = sum(income.mapped(amount_field))
                mercancia = sum(inv_inicial.mapped(amount_field)) + sum(compras.mapped(amount_field))
                costo_venta = mercancia - sum(inv_final.mapped(amount_field))
                renta_bruta = ingresos - costo_venta
                deducciones = sum(deductions.mapped(amount_field))
                utilidad = renta_bruta - deducciones
                setattr(record, f'total_ingresos_{suffix}', ingresos)
                setattr(record, f'mercancia_disponible_{suffix}', mercancia)
                setattr(record, f'total_costo_venta_{suffix}', costo_venta)
                setattr(record, f'renta_bruta_{suffix}', renta_bruta)
                setattr(record, f'total_deducciones_{suffix}', deducciones)
                setattr(record, f'utilidad_neta_{suffix}', utilidad)
            record.monto_a_pagar_calculado = TOTAL_TAX_RATE * record.utilidad_neta_fiscal

    @api.depends(
        'total_ingresos_accounting',
        'total_ingresos_fiscal',
        'mercancia_disponible_accounting',
        'mercancia_disponible_fiscal',
        'total_costo_venta_accounting',
        'total_costo_venta_fiscal',
        'renta_bruta_accounting',
        'renta_bruta_fiscal',
        'total_deducciones_accounting',
        'total_deducciones_fiscal',
        'utilidad_neta_accounting',
        'utilidad_neta_fiscal',
        'monto_a_pagar_calculado',
        'totals_xlsx',
        'monto_a_pagar_xlsx',
        'import_meta',
        'line_ids.label',
        'line_ids.code',
        'line_ids.amount_accounting',
        'line_ids.amount_fiscal',
        'line_ids.amount_not_deductible',
    )
    def _compute_warning_html(self):
        for record in self:
            warnings = record._collect_warnings()
            if not warnings:
                record.warning_html = False
                continue
            items = Markup('').join(
                Markup('<li>%s</li>') % escape(warning) for warning in warnings
            )
            record.warning_html = Markup('<ul>%s</ul>') % items

    def _collect_warnings(self):
        """Retorna la lista de advertencias (mensajes) del registro."""
        self.ensure_one()
        warnings = []
        totals_xlsx = self.totals_xlsx or {}
        for key, field_names in TOTAL_FIELDS.items():
            reference = totals_xlsx.get(key) or {}
            for suffix, field_name in zip(('accounting', 'fiscal'), field_names):
                xlsx_value = reference.get(suffix)
                if xlsx_value is None:
                    continue
                recalculated = self[field_name]
                if abs(recalculated - xlsx_value) > 0.01:
                    warnings.append(
                        f'Descuadre en "{WARNING_TOTAL_LABELS[key]}" ({SIDE_LABELS[suffix]}): '
                        f'el sistema recalcula Bs {recalculated:,.2f} '
                        f'y el Excel informa Bs {xlsx_value:,.2f}'
                    )

        for line in self.line_ids:
            expected = line.amount_fiscal + line.amount_not_deductible
            if abs(line.amount_accounting - expected) > 0.01:
                warnings.append(
                    f'La línea "{line.label}" no cumple la identidad '
                    f'contabilidad = fiscal + no deducible '
                    f'(Bs {line.amount_accounting:,.2f} ≠ Bs {expected:,.2f})'
                )

        sueldos_fiscal = sum(
            self.line_ids.filtered(lambda line: line.code == 'sueldos_directivos')
            .mapped('amount_fiscal')
        )
        if sueldos_fiscal > 0.01:
            tope = self.total_ingresos_fiscal * 0.10
            if self.total_ingresos_fiscal <= 0:
                warnings.append(
                    'No hay ingresos fiscales: no se pudo validar el tope del 10% '
                    'de sueldos directivos'
                )
            elif sueldos_fiscal > tope + 0.01:
                warnings.append(
                    f'Los sueldos directivos (Bs {sueldos_fiscal:,.2f}) superan '
                    f'el tope del 10% de los ingresos brutos (Bs {tope:,.2f})'
                )

        monto_informado = self.monto_a_pagar_xlsx or 0.0
        if abs(self.monto_a_pagar_calculado - monto_informado) > 0.01:
            warnings.append(
                f'Monto a pagar calculado (Bs {self.monto_a_pagar_calculado:,.2f}) '
                f'no coincide con el informado en el Excel (Bs {monto_informado:,.2f})'
            )

        for line in self.line_ids.filtered(lambda line: line.code == 'otro'):
            warnings.append(f'Rubro sin mapeo: "{line.label}" se importó como "Otro"')

        meta = self.import_meta or {}
        for duplicate in meta.get('duplicates') or []:
            warnings.append(f'Rubro duplicado en el Excel: "{duplicate}" (importes sumados)')
        text_cells = meta.get('text_cells') or []
        if text_cells:
            warnings.append(
                f'Celdas con texto en columnas numéricas: {", ".join(text_cells)} (se usó 0.00)'
            )
        return warnings

    def write(self, vals):
        """Actualiza campos de auditoría al editar manualmente."""
        if 'modified_by' not in vals:
            vals['modified_by'] = self.env.user.id
        vals['modified_at'] = fields.Datetime.now()
        return super().write(vals)

    @api.depends('import_meta')
    def _compute_import_trace(self):
        for record in self:
            meta = record.import_meta or {}
            record.source_file = meta.get('source_file') or ''
            record.imported_by = meta.get('imported_by') or ''
            raw = str(meta.get('imported_at') or '').replace('T', ' ')
            record.imported_at = fields.Datetime.to_datetime(raw) or False

    def action_validate(self):
        """Marca la conciliación como validada."""
        self.write({'state': 'validated'})

    def action_revert_draft(self):
        """Devuelve la conciliación a borrador."""
        self.write({'state': 'draft'})

    _unique_client_year = models.Constraint(
        'UNIQUE(client_id, company_id, fiscal_year)',
        'Ya existe una conciliación ISLR para este cliente, compañía y año fiscal.',
    )


class IslrReconciliationLine(models.Model):
    _name = 'l10n.ve.islr.reconciliation.line'
    _description = 'Línea de Conciliación Fiscal ISLR'
    _order = 'reconciliation_id, sequence, id'

    reconciliation_id = fields.Many2one(
        'l10n.ve.islr.reconciliation',
        string='Conciliación',
        required=True,
        ondelete='cascade',
        index=True,
    )

    sequence = fields.Integer(string='Secuencia', default=10)

    category = fields.Selection([
        ('income', 'Ingresos'),
        ('cost', 'Costos de Venta'),
        ('deduction', 'Deducciones'),
    ], string='Categoría', required=True, index=True)

    code = fields.Selection([
        ('ventas', 'Ventas'),
        ('inventario_inicial', 'Inventario Inicial de Mercancía'),
        ('compras_mercancia', 'Compras de Mercancías'),
        ('inventario_final', 'Inventario Final'),
        ('sueldos_directivos', 'Sueldos y Salarios del Personal Directivo y Gerencial'),
        ('tributos_pagados', 'Tributos Pagados'),
        ('arrendamientos', 'Arrendamientos'),
        ('otros_gastos', 'Otros Gastos'),
        ('gastos_representacion', 'Gastos de Representación'),
        ('gastos_generales', 'Gastos Generales'),
        ('gastos_transporte', 'Gastos de Transporte'),
        ('gastos_trabajo', 'Gastos de Trabajo'),
        ('gastos_reparaciones', 'Gastos de Reparaciones'),
        ('servicios_internet', 'Servicios de Internet'),
        ('gastos_depreciacion', 'Gastos de Depreciación'),
        ('otro', 'Otro'),
    ], string='Rubro', required=True, default='otro', index=True)

    label = fields.Char(string='Descripción', required=True)

    amount_accounting = fields.Float(
        string='Datos Contabilidad',
        digits='Account',
    )

    amount_fiscal = fields.Float(
        string='Datos Fiscales',
        digits='Account',
    )

    amount_not_deductible = fields.Float(
        string='No Gravable o No Deducible',
        digits='Account',
    )

    legal_basis = fields.Char(string='Preceptos Legales')

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='reconciliation_id.company_id',
        store=True,
        index=True,
    )

    modified_by = fields.Many2one(
        'res.users',
        string='Modificado por',
    )

    modified_at = fields.Datetime(
        string='Modificado en',
        readonly=True,
    )

    def write(self, vals):
        """Actualiza campos de auditoría al editar manualmente."""
        if 'modified_by' not in vals:
            vals['modified_by'] = self.env.user.id
        vals['modified_at'] = fields.Datetime.now()
        return super().write(vals)
