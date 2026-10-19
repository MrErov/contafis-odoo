from odoo import api, fields, models


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

    def write(self, vals):
        """Actualiza campos de auditoría al editar manualmente."""
        if 'modified_by' not in vals:
            vals['modified_by'] = self.env.user.id
        vals['modified_at'] = fields.Datetime.now()
        return super().write(vals)

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
