from io import BytesIO
from pathlib import Path

from odoo.addons.l10n_ve_compliance_manager.models.islr_conciliation import (
    IslrParseError,
    normalize_label,
    parse_conciliacion_xlsx,
    sanitize_rif,
    to_amount,
)
from odoo.tests import TransactionCase, tagged
from openpyxl import Workbook
from psycopg2 import IntegrityError

FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx'


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


@tagged('post_install', '-at_install')
class TestIslrParserHelpers(TransactionCase):
    """Funciones puras del parser (Spec 011 — T2)."""

    def test_sanitize_rif(self):
        self.assertEqual(sanitize_rif('J-99999999-0'), 'J999999990')
        self.assertEqual(sanitize_rif('j.99999999.0'), 'J999999990')
        self.assertEqual(sanitize_rif(' V-12 345 678-1 '), 'V123456781')
        self.assertEqual(sanitize_rif(''), '')
        self.assertEqual(sanitize_rif(None), '')

    def test_normalize_label(self):
        self.assertEqual(normalize_label('  Período   FISCAL '), 'periodo fiscal')
        self.assertEqual(normalize_label('Gastos de Depreciación'), 'gastos de depreciacion')
        self.assertEqual(normalize_label('otros gastos '), 'otros gastos')
        self.assertEqual(normalize_label(None), '')

    def test_to_amount(self):
        self.assertEqual(to_amount(123.45), (123.45, False))
        self.assertEqual(to_amount(None), (0.0, False))
        self.assertEqual(to_amount(''), (0.0, False))
        self.assertEqual(to_amount('1234.5'), (1234.5, False))
        self.assertEqual(to_amount('SIN ACTIVIDAD'), (0.0, True))


@tagged('post_install', '-at_install')
class TestParseConciliacionFixture(TransactionCase):
    """Parser sobre el fixture real (Spec 011 — T2, RF-1/3/4/5/15/16)."""

    def setUp(self):
        super().setUp()
        self.data = parse_conciliacion_xlsx(FIXTURE_PATH.read_bytes())

    def test_periodo_y_rif(self):
        self.assertEqual(self.data['fiscal_year'], 2025)
        self.assertEqual(self.data['rif'], 'J-99999999-0')
        self.assertEqual(sanitize_rif(self.data['rif']), 'J999999990')

    def test_rubros_del_bloque_principal(self):
        labels = [r['label'] for r in self.data['rubros']]
        self.assertEqual(len(labels), 10)
        self.assertEqual(labels[0], 'Ventas')
        self.assertEqual(labels[-1], 'gastos de transporte')
        self.assertEqual(self.data['rubros'][0]['sequence'], 14)

    def test_ventas(self):
        ventas = self.data['rubros'][0]
        self.assertEqual(ventas['code'], 'ventas')
        self.assertEqual(ventas['category'], 'income')
        self.assertEqual(ventas['accounting'], 1991278.8)
        self.assertEqual(ventas['fiscal'], 1991278.8)
        self.assertEqual(ventas['not_deductible'], 0)
        self.assertEqual(ventas['legal_basis'], 'Art. 5 LISLR')

    def test_costos(self):
        by_label = {r['label']: r for r in self.data['rubros']}
        inv_ini = by_label['Inventario Inicial de Mercancía']
        self.assertEqual(inv_ini['code'], 'inventario_inicial')
        self.assertEqual(inv_ini['category'], 'cost')
        self.assertEqual(inv_ini['accounting'], 193704.75)
        self.assertEqual(by_label['Compras de Mercancías']['accounting'], 1788584.01)
        self.assertEqual(by_label['Inventario Final']['fiscal'], 598486.5)

    def test_deducciones(self):
        by_code = {r['code']: r for r in self.data['rubros']}
        self.assertEqual(by_code['sueldos_directivos']['fiscal'], 60747.65)
        self.assertEqual(by_code['sueldos_directivos']['not_deductible'], 17082.1)
        self.assertEqual(by_code['tributos_pagados']['accounting'], 51096.57)
        self.assertEqual(by_code['arrendamientos']['accounting'], 0)
        self.assertEqual(by_code['otros_gastos']['accounting'], 56053.12)
        self.assertEqual(by_code['gastos_representacion']['accounting'], 58708.12)
        self.assertEqual(by_code['gastos_transporte']['fiscal'], 168954.75)

    def test_totales_de_referencia(self):
        totals = self.data['totals']
        self.assertEqual(totals['total_ingresos']['accounting'], 1991278.8)
        self.assertEqual(totals['mercancia_disponible']['fiscal'], 1982288.76)
        self.assertEqual(totals['total_costo_venta']['accounting'], 1383802.26)
        self.assertEqual(totals['renta_bruta']['accounting'], 607476.54)
        self.assertEqual(totals['total_deducciones']['accounting'], 184979.44)
        self.assertEqual(totals['total_deducciones']['fiscal'], 395560.22)
        self.assertEqual(totals['utilidad_neta']['accounting'], 422497.1)
        self.assertEqual(totals['utilidad_neta']['fiscal'], 211916.32)

    def test_monto_a_pagar(self):
        self.assertEqual(self.data['monto_a_pagar_xlsx'], 47863.69)

    def test_totales_no_son_rubros(self):
        labels = ' | '.join(r['label'] for r in self.data['rubros']).upper()
        for token in ('TOTAL', 'MERCANCIA DISPONIBLE', 'RENTA BRUTA', 'UTILIDAD NETA'):
            self.assertNotIn(token, labels)

    def test_bloques_laterales_ignorados(self):
        labels = ' | '.join(r['label'] for r in self.data['rubros']).upper()
        for token in ('SIN ACTIVIDAD', 'ENERO', 'DECLARACION'):
            self.assertNotIn(token, labels)

    def test_sin_textos_ni_duplicados(self):
        self.assertEqual(self.data['text_cells'], [])
        self.assertEqual(self.data['duplicates'], [])


@tagged('post_install', '-at_install')
class TestParseConciliacionSynthetic(TransactionCase):
    """Casos límite del parser con archivos sintéticos (Spec 011 — T2)."""

    def _build_bytes(self, cells, sheet_name='Conciliación Fiscal'):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_name
        for coord, value in cells.items():
            sheet[coord] = value
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def _base_cells(self):
        return {
            'B5': 'Empresa Demo',
            'B6': 'Período Fiscal del 01/01/2025 al 31/12/2025',
            'E11': 'RIF J-99999999-0',
            'B12': 'Descripción',
            'B13': 'INGRESOS',
            'B14': 'Ventas',
            'C14': 1000.0,
            'D14': 900.0,
            'E14': 100.0,
        }

    def test_hoja_case_insensitive(self):
        content = self._build_bytes(self._base_cells(), sheet_name='CONCILIACIÓN FISCAL')
        data = parse_conciliacion_xlsx(content)
        self.assertEqual(len(data['rubros']), 1)

    def test_hoja_ausente(self):
        content = self._build_bytes(self._base_cells(), sheet_name='Otra Hoja')
        with self.assertRaises(IslrParseError):
            parse_conciliacion_xlsx(content)

    def test_archivo_corrupto(self):
        with self.assertRaises(IslrParseError):
            parse_conciliacion_xlsx(b'esto no es un xlsx')

    def test_anio_ausente(self):
        cells = self._base_cells()
        del cells['B6']
        with self.assertRaises(IslrParseError):
            parse_conciliacion_xlsx(self._build_bytes(cells))

    def test_rif_ausente(self):
        cells = self._base_cells()
        del cells['E11']
        with self.assertRaises(IslrParseError):
            parse_conciliacion_xlsx(self._build_bytes(cells))

    def test_texto_en_celda_numerica(self):
        cells = self._base_cells()
        cells['C14'] = 'SIN ACTIVIDAD'
        data = parse_conciliacion_xlsx(self._build_bytes(cells))
        self.assertEqual(data['rubros'][0]['accounting'], 0.0)
        self.assertIn('C14', data['text_cells'])

    def test_duplicados_se_suman(self):
        cells = self._base_cells()
        cells['B15'] = 'VENTAS '
        cells['C15'] = 500.0
        cells['D15'] = 100.0
        data = parse_conciliacion_xlsx(self._build_bytes(cells))
        self.assertEqual(len(data['rubros']), 1)
        self.assertEqual(data['rubros'][0]['accounting'], 1500.0)
        self.assertEqual(data['rubros'][0]['fiscal'], 1000.0)
        self.assertTrue(data['duplicates'])

    def test_rubro_desconocido(self):
        cells = self._base_cells()
        cells['B14'] = 'Rubro Raro'
        data = parse_conciliacion_xlsx(self._build_bytes(cells))
        self.assertEqual(data['rubros'][0]['code'], 'otro')
        self.assertEqual(data['rubros'][0]['category'], 'income')
