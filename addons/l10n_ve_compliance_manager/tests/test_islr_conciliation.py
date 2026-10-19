import base64
from io import BytesIO
from pathlib import Path

from odoo import fields
from odoo.addons.l10n_ve_compliance_manager.models.islr_conciliation import (
    IslrParseError,
    normalize_label,
    parse_conciliacion_xlsx,
    sanitize_rif,
    to_amount,
)
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from openpyxl import Workbook
from psycopg2 import IntegrityError

FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx'


def build_synthetic_workbook(cells, sheet_name='Conciliación Fiscal'):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for coord, value in cells.items():
        sheet[coord] = value
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


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
        return build_synthetic_workbook(cells, sheet_name)

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


@tagged('post_install', '-at_install')
class TestIslrConciliacionTotals(TransactionCase):
    """Computes de totales y advertencias (Spec 011 — T3, RF-7 a RF-11, RF-17)."""

    def setUp(self):
        super().setUp()
        self.env['l10n.ve.islr.reconciliation.line'].search([]).unlink()
        self.env['l10n.ve.islr.reconciliation'].search([]).unlink()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Totales Test',
            'vat': 'J-12345678-9',
        })
        self.client = self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Totales Test',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-12345678-9',
        })
        self.Reconciliacion = self.env['l10n.ve.islr.reconciliation']
        self.Line = self.env['l10n.ve.islr.reconciliation.line']

    def _create_reconciliation(self):
        return self.Reconciliacion.create({
            'client_id': self.client.id,
            'company_id': self.env.company.id,
            'fiscal_year': 2025,
        })

    def _add_line(self, rec, code, category, accounting, fiscal, not_deductible=0.0, label=None):
        return self.Line.create({
            'reconciliation_id': rec.id,
            'code': code,
            'category': category,
            'label': label or code,
            'amount_accounting': accounting,
            'amount_fiscal': fiscal,
            'amount_not_deductible': not_deductible,
        })

    def _simple_reconciliation(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'ventas', 'income', 1000.0, 900.0)
        self._add_line(rec, 'inventario_inicial', 'cost', 100.0, 80.0)
        self._add_line(rec, 'compras_mercancia', 'cost', 300.0, 300.0)
        self._add_line(rec, 'inventario_final', 'cost', 50.0, 50.0)
        self._add_line(rec, 'sueldos_directivos', 'deduction', 40.0, 30.0)
        return rec

    def test_computes_basicos(self):
        rec = self._simple_reconciliation()
        self.assertEqual(rec.total_ingresos_accounting, 1000.0)
        self.assertEqual(rec.total_ingresos_fiscal, 900.0)
        self.assertEqual(rec.mercancia_disponible_accounting, 400.0)
        self.assertEqual(rec.mercancia_disponible_fiscal, 380.0)
        self.assertEqual(rec.total_costo_venta_accounting, 350.0)
        self.assertEqual(rec.total_costo_venta_fiscal, 330.0)
        self.assertEqual(rec.renta_bruta_accounting, 650.0)
        self.assertEqual(rec.renta_bruta_fiscal, 570.0)
        self.assertEqual(rec.total_deducciones_accounting, 40.0)
        self.assertEqual(rec.total_deducciones_fiscal, 30.0)
        self.assertEqual(rec.utilidad_neta_accounting, 610.0)
        self.assertEqual(rec.utilidad_neta_fiscal, 540.0)
        self.assertEqual(round(rec.monto_a_pagar_calculado, 2), 183.6)

    def test_recalculo_al_editar_linea(self):
        rec = self._simple_reconciliation()
        line = rec.line_ids.filtered(lambda line: line.code == 'ventas')
        line.write({'amount_accounting': 1500.0, 'amount_fiscal': 1400.0})
        self.assertEqual(rec.total_ingresos_accounting, 1500.0)
        self.assertEqual(rec.mercancia_disponible_accounting, 400.0)
        self.assertEqual(rec.utilidad_neta_accounting, 1110.0)

    def test_warning_descuadre_contra_excel(self):
        rec = self._simple_reconciliation()
        rec.write({'totals_xlsx': {'total_deducciones': {'accounting': 999.0, 'fiscal': 30.0}}})
        self.assertIn('Descuadre en', rec.warning_html)
        self.assertIn('Total deducciones', rec.warning_html)
        self.assertIn('(contabilidad)', rec.warning_html)
        rec.write({'totals_xlsx': {'total_deducciones': {'accounting': 40.0, 'fiscal': 30.0}}})
        self.assertNotIn('Total deducciones', rec.warning_html or '')

    def test_warning_identidad(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'ventas', 'income', 1000.0, 900.0)
        self.assertIn('identidad', rec.warning_html)

    def test_warning_tope_diez_por_ciento(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'ventas', 'income', 100.0, 100.0)
        self._add_line(rec, 'sueldos_directivos', 'deduction', 20.0, 20.0)
        self.assertIn('tope del 10%', rec.warning_html)

    def test_warning_tope_sin_base(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'ventas', 'income', 100.0, 0.0)
        self._add_line(rec, 'sueldos_directivos', 'deduction', 5.0, 5.0)
        self.assertIn('No hay ingresos fiscales', rec.warning_html)

    def test_warning_monto(self):
        rec = self._simple_reconciliation()
        rec.write({'monto_a_pagar_xlsx': 100.0})
        self.assertIn('Monto a pagar calculado', rec.warning_html)
        self.assertIn('183.60', rec.warning_html)

    def test_warning_rubro_desconocido(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'otro', 'deduction', 10.0, 10.0, label='Rubro Raro')
        self.assertIn('Rubro sin mapeo', rec.warning_html)

    def test_warning_duplicado_y_texto(self):
        rec = self._simple_reconciliation()
        rec.write({'import_meta': {'duplicates': ['ventas'], 'text_cells': ['C14', 'D15']}})
        self.assertIn('duplicado', rec.warning_html)
        self.assertIn('C14', rec.warning_html)

    def test_warning_html_false_cuando_todo_cuadra(self):
        rec = self._create_reconciliation()
        self._add_line(rec, 'ventas', 'income', 1000.0, 1000.0)
        self._add_line(rec, 'inventario_inicial', 'cost', 100.0, 100.0)
        self._add_line(rec, 'compras_mercancia', 'cost', 300.0, 300.0)
        self._add_line(rec, 'inventario_final', 'cost', 50.0, 50.0)
        self._add_line(rec, 'sueldos_directivos', 'deduction', 40.0, 40.0)
        rec.write({
            'totals_xlsx': {
                'total_ingresos': {'accounting': 1000.0, 'fiscal': 1000.0},
                'mercancia_disponible': {'accounting': 400.0, 'fiscal': 400.0},
                'total_costo_venta': {'accounting': 350.0, 'fiscal': 350.0},
                'renta_bruta': {'accounting': 650.0, 'fiscal': 650.0},
                'total_deducciones': {'accounting': 40.0, 'fiscal': 40.0},
                'utilidad_neta': {'accounting': 610.0, 'fiscal': 610.0},
            },
            'monto_a_pagar_xlsx': 207.4,
        })
        self.assertFalse(rec.warning_html)

    def test_fixture_advertencias_esperadas(self):
        data = parse_conciliacion_xlsx(FIXTURE_PATH.read_bytes())
        rec = self._create_reconciliation()
        for rubro in data['rubros']:
            self.Line.create({
                'reconciliation_id': rec.id,
                'sequence': rubro['sequence'],
                'code': rubro['code'],
                'category': rubro['category'],
                'label': rubro['label'],
                'amount_accounting': rubro['accounting'],
                'amount_fiscal': rubro['fiscal'],
                'amount_not_deductible': rubro['not_deductible'],
                'legal_basis': rubro['legal_basis'] or False,
            })
        rec.write({
            'totals_xlsx': data['totals'],
            'monto_a_pagar_xlsx': data['monto_a_pagar_xlsx'],
            'import_meta': {
                'duplicates': data['duplicates'],
                'text_cells': data['text_cells'],
            },
        })
        html = rec.warning_html
        self.assertIn('Total deducciones', html)
        self.assertIn('Utilidad neta', html)
        self.assertIn('(contabilidad)', html)
        self.assertIn('Monto a pagar calculado', html)
        self.assertIn('72,051.55', html)
        self.assertNotIn('(fiscal)', html)
        self.assertNotIn('tope del 10%', html)
        self.assertNotIn('identidad', html)
        self.assertNotIn('Rubro sin mapeo', html)


class IslrWizardTestMixin:
    """Helpers compartidos por los tests del wizard de conciliación ISLR."""

    def _islr_wizard_setup(self):
        self.env['l10n.ve.islr.reconciliation.line'].search([]).unlink()
        self.env['l10n.ve.islr.reconciliation'].search([]).unlink()
        self.env['l10n.ve.import.wizard'].search([]).unlink()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Wizard ISLR',
            'vat': 'J-99999999-0',
        })
        self.client = self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Wizard ISLR',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-99999999-0',
        })

    def _create_wizard(self, **vals):
        base = {
            'import_type': 'islr_conciliation',
            'company_id': self.env.company.id,
        }
        base.update(vals)
        return self.env['l10n.ve.import.wizard'].create(base)

    def _load_bytes(self, wizard, content, filename='conciliacion.xlsx'):
        wizard.write({
            'file': base64.b64encode(content),
            'filename': filename,
        })
        return wizard.action_load_file()


@tagged('post_install', '-at_install')
class TestIslrConciliacionWizardLoad(IslrWizardTestMixin, TransactionCase):
    """Wizard de importación: carga de conciliación ISLR (Spec 011 — T4)."""

    def setUp(self):
        super().setUp()
        self._islr_wizard_setup()

    def test_tipo_disponible(self):
        selection = self.env['l10n.ve.import.wizard']._fields['import_type'].selection
        values = [value for value, _label in selection]
        self.assertIn('islr_conciliation', values)

    def test_carga_fixture_detecta_cliente_anio_y_rubros(self):
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertEqual(wizard.state, 'preview')
        self.assertEqual(wizard.conciliacion_client_id, self.client)
        self.assertEqual(wizard.conciliacion_fiscal_year, 2025)
        self.assertFalse(wizard.conciliacion_existing_id)
        self.assertFalse(wizard.replace_confirmed)
        self.assertIn('10 rubros', wizard.conciliacion_summary)
        self.assertEqual(len(wizard.conciliacion_data['rubros']), 10)

    def test_resumen_incluye_utilidad_fiscal(self):
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertIn('211,916.32', wizard.conciliacion_summary)

    def test_rif_normalizado_sin_guiones(self):
        self.client.rif = 'j.99999999-0'
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertEqual(wizard.conciliacion_client_id, self.client)

    def test_existente_detectado_requiere_confirmacion(self):
        existing = self.env['l10n.ve.islr.reconciliation'].create({
            'client_id': self.client.id,
            'company_id': self.env.company.id,
            'fiscal_year': 2025,
        })
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertEqual(wizard.conciliacion_existing_id, existing)
        self.assertEqual(wizard.state, 'preview')
        self.assertFalse(wizard.replace_confirmed)

    def test_rif_inexistente_aborta(self):
        cells = {
            'B5': 'Empresa Demo',
            'B6': 'Período Fiscal del 01/01/2025 al 31/12/2025',
            'E11': 'RIF J-00000000-1',
            'B13': 'INGRESOS',
            'B14': 'Ventas',
            'C14': 10.0,
            'D14': 10.0,
        }
        wizard = self._create_wizard()
        with self.assertRaises(UserError) as caught:
            self._load_bytes(wizard, build_synthetic_workbook(cells))
        self.assertIn('no está registrado', str(caught.exception))
        self.assertEqual(wizard.state, 'draft')
        self.assertFalse(wizard.conciliacion_client_id)

    def _create_second_company_client(self):
        company_b = self.env['res.company'].create({'name': 'Compañía ISLR B'})
        self.env.user.write({'company_ids': [(4, company_b.id)]})
        partner_b = self.env['res.partner'].create({
            'name': 'Cliente Wizard ISLR B',
            'vat': 'J-99999999-0',
        })
        client_b = self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Wizard ISLR B',
            'partner_id': partner_b.id,
            'company_id': company_b.id,
            'rif': 'J-99999999-0',
        })
        return company_b, client_b

    def test_compania_ambigua_se_resuelve_con_la_del_wizard(self):
        company_b, client_b = self._create_second_company_client()
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertEqual(wizard.conciliacion_client_id, self.client)
        wizard.write({'company_id': company_b.id})
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertEqual(wizard.conciliacion_client_id, client_b)

    def test_compania_ambigua_sin_match_aborta(self):
        _company_b, _client_b = self._create_second_company_client()
        company_c = self.env['res.company'].create({'name': 'Compañía ISLR C'})
        self.env.user.write({'company_ids': [(4, company_c.id)]})
        wizard = self._create_wizard(company_id=company_c.id)
        with self.assertRaises(UserError) as caught:
            self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertIn('varias compañías', str(caught.exception))
        self.assertEqual(wizard.state, 'draft')
        self.assertFalse(wizard.conciliacion_client_id)

    def test_hoja_ausente_user_error(self):
        wizard = self._create_wizard()
        with self.assertRaises(UserError) as caught:
            self._load_bytes(
                wizard,
                build_synthetic_workbook({'B5': 'X'}, sheet_name='Otra Hoja'),
            )
        self.assertIn('Conciliación Fiscal', str(caught.exception))

    def test_archivo_corrupto_user_error(self):
        wizard = self._create_wizard()
        with self.assertRaises(UserError) as caught:
            self._load_bytes(wizard, b'no es un xlsx')
        self.assertIn('No se pudo abrir', str(caught.exception))

    def test_falta_archivo_user_error(self):
        wizard = self._create_wizard()
        with self.assertRaises(UserError):
            wizard.action_load_file()


@tagged('post_install', '-at_install')
class TestIslrConciliacionWizardImport(IslrWizardTestMixin, TransactionCase):
    """Wizard: importación, reemplazo y trazabilidad (Spec 011 — T5)."""

    def setUp(self):
        super().setUp()
        self._islr_wizard_setup()
        self.Reconciliacion = self.env['l10n.ve.islr.reconciliation']

    def _find_record(self):
        return self.Reconciliacion.search([
            ('client_id', '=', self.client.id),
            ('fiscal_year', '=', 2025),
        ])

    def _import_fixture(self):
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        wizard.action_import()
        return wizard

    def test_import_crea_registro_draft_con_lineas(self):
        wizard = self._import_fixture()
        record = self._find_record()
        self.assertEqual(len(record), 1)
        self.assertEqual(record.state, 'draft')
        self.assertEqual(len(record.line_ids), 10)
        self.assertAlmostEqual(record.utilidad_neta_fiscal, 211916.32, delta=0.02)
        self.assertEqual(record.monto_a_pagar_xlsx, 47863.69)
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.conciliacion_existing_id, record)

    def test_import_trazabilidad_del_archivo(self):
        self._import_fixture()
        record = self._find_record()
        meta = record.import_meta
        self.assertEqual(meta['source_file'], 'conciliacion.xlsx')
        self.assertEqual(meta['imported_by'], self.env.user.login)
        self.assertTrue(meta['imported_at'])
        self.assertIn('duplicates', meta)
        self.assertIn('text_cells', meta)

    def test_sin_datos_cargados_aborta(self):
        wizard = self._create_wizard()
        with self.assertRaises(UserError) as caught:
            wizard.action_import()
        self.assertIn('Cargue', str(caught.exception))

    def test_reimportar_sin_confirmar_aborta(self):
        self._import_fixture()
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertTrue(wizard.conciliacion_existing_id)
        with self.assertRaises(UserError) as caught:
            wizard.action_import()
        message = str(caught.exception)
        self.assertIn('Confirmar Reemplazo', message)
        record = self._find_record()
        self.assertEqual(len(record), 1)
        self.assertEqual(len(record.line_ids), 10)

    def test_reimportar_confirmado_reemplaza_sin_duplicar(self):
        self._import_fixture()
        record = self._find_record()
        ventas = record.line_ids.filtered(lambda line: line.code == 'ventas')
        ventas.write({'amount_accounting': 999.0, 'amount_fiscal': 999.0})
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        wizard.replace_confirmed = True
        wizard.action_import()
        record = self._find_record()
        self.assertEqual(len(record), 1)
        self.assertEqual(len(record.line_ids), 10)
        ventas = record.line_ids.filtered(lambda line: line.code == 'ventas')
        self.assertEqual(len(ventas), 1)
        self.assertEqual(ventas.amount_fiscal, 1991278.8)
        self.assertEqual(record.modified_by, self.env.user)
        self.assertTrue(record.modified_at)

    def test_reimportar_validado_reinicia_borrador_y_borra_pdf(self):
        self._import_fixture()
        record = self._find_record()
        attachment = self.env['ir.attachment'].create({
            'name': 'conciliacion.pdf',
            'datas': base64.b64encode(b'pdf'),
            'res_model': record._name,
            'res_id': record.id,
        })
        record.write({'state': 'validated', 'pdf_attachment_id': attachment.id})
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        wizard.replace_confirmed = True
        wizard.action_import()
        self.assertEqual(record.state, 'draft')
        self.assertFalse(record.pdf_attachment_id)
        self.assertFalse(attachment.exists())

    def test_rif_con_formato_distinto_advierte_al_confirmar(self):
        self.client.rif = 'J999999990'
        self._import_fixture()
        wizard = self._create_wizard()
        self._load_bytes(wizard, FIXTURE_PATH.read_bytes())
        self.assertTrue(wizard.conciliacion_existing_id)
        with self.assertRaises(UserError) as caught:
            wizard.action_import()
        message = str(caught.exception)
        self.assertIn('Confirmar Reemplazo', message)
        self.assertIn('RIF del archivo', message)
        wizard.replace_confirmed = True
        wizard.action_import()
        record = self._find_record()
        self.assertEqual(
            record.import_meta['rif_mismatch']['sheet'], 'J-99999999-0'
        )
        self.assertEqual(
            record.import_meta['rif_mismatch']['client'], 'J999999990'
        )


@tagged('post_install', '-at_install')
class TestIslrConciliacionViews(IslrWizardTestMixin, TransactionCase):
    """Vistas, acción, menú y trazabilidad visible (Spec 011 — T6)."""

    def setUp(self):
        super().setUp()
        self._islr_wizard_setup()
        self.Reconciliacion = self.env['l10n.ve.islr.reconciliation']

    def test_accion_principal(self):
        action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_islr_conciliation'
        )
        self.assertEqual(action.res_model, 'l10n.ve.islr.reconciliation')
        self.assertIn('list', action.view_mode)
        self.assertIn('form', action.view_mode)

    def test_accion_wizard_incluye_tipo_islr(self):
        action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_islr_conciliation_import'
        )
        self.assertEqual(action.res_model, 'l10n.ve.import.wizard')
        self.assertEqual(action.target, 'new')
        self.assertIn('islr_conciliation', action.context)

    def test_menu_conciliacion_islr(self):
        menu = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_islr_conciliation'
        )
        root = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_compliance_root'
        )
        self.assertEqual(menu.parent_id, root)
        self.assertEqual(menu.sequence, 42)
        self.assertEqual(
            menu.action.id,
            self.env.ref(
                'l10n_ve_compliance_manager.action_l10n_ve_islr_conciliation'
            ).id,
        )
        self.assertEqual(menu.action.res_model, 'l10n.ve.islr.reconciliation')

    def test_load_menus_incluye_conciliacion(self):
        menus = self.env['ir.ui.menu'].with_user(
            self.env.ref('base.user_admin')
        ).load_menus(False)

        def _find(nodes):
            for node in nodes.values():
                if not isinstance(node, dict):
                    continue
                if node.get('name') == 'Conciliación ISLR':
                    return node
                for child in node.get('children') or []:
                    if isinstance(child, dict):
                        if child.get('name') == 'Conciliación ISLR':
                            return child
                    else:
                        child_node = nodes.get(child)
                        if (
                            child_node
                            and child_node.get('name') == 'Conciliación ISLR'
                        ):
                            return child_node
            return None

        self.assertTrue(_find(menus))

    def test_vistas_list_y_form_cargan(self):
        result = self.Reconciliacion.get_views([(False, 'list'), (False, 'form')])
        self.assertIn('list', result['views'])
        self.assertIn('form', result['views'])
        form_arch = result['views']['form']['arch']
        for field_name in (
            'warning_html',
            'line_ids',
            'total_ingresos_accounting',
            'total_ingresos_fiscal',
            'monto_a_pagar_calculado',
            'source_file',
            'imported_by',
            'imported_at',
        ):
            self.assertIn(field_name, form_arch)
        list_arch = result['views']['list']['arch']
        for field_name in (
            'client_id',
            'fiscal_year',
            'state',
            'utilidad_neta_fiscal',
        ):
            self.assertIn(field_name, list_arch)

    def test_vista_busqueda_carga(self):
        result = self.Reconciliacion.get_views([(False, 'search')])
        arch = result['views']['search']['arch']
        self.assertIn('fiscal_year', arch)
        self.assertIn('group_by', arch)

    def test_wizard_form_incluye_seccion_islr(self):
        result = self.env['l10n.ve.import.wizard'].get_views([(False, 'form')])
        arch = result['views']['form']['arch']
        for field_name in (
            'conciliacion_client_id',
            'conciliacion_fiscal_year',
            'conciliacion_existing_id',
            'replace_confirmed',
        ):
            self.assertIn(field_name, arch)

    def test_campos_trazabilidad_calculados(self):
        record = self.Reconciliacion.create({
            'client_id': self.client.id,
            'company_id': self.env.company.id,
            'fiscal_year': 2025,
            'import_meta': {
                'source_file': 'conciliacion-demo.xlsx',
                'imported_by': 'admin',
                'imported_at': '2026-10-19T20:00:00',
            },
        })
        self.assertEqual(record.source_file, 'conciliacion-demo.xlsx')
        self.assertEqual(record.imported_by, 'admin')
        self.assertEqual(
            record.imported_at,
            fields.Datetime.to_datetime('2026-10-19 20:00:00'),
        )
