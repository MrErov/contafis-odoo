from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from lxml import etree
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import convert
from odoo.tools.safe_eval import safe_eval
from psycopg2 import IntegrityError

TEST_YEAR = 2099  # año libre de la precarga oficial (2026)


@tagged('post_install', '-at_install')
class TestSeniatCalendarModels(TransactionCase):
    """T1: modelos del calendario SENIAT (tabla por año + líneas mes/dígito)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CalendarTable = cls.env['l10n.ve.seniat.calendar.table']
        cls.CalendarLine = cls.env['l10n.ve.seniat.calendar']

    def _create_table(self, **kwargs):
        vals = {'year': TEST_YEAR, 'code': 'a1'}
        vals.update(kwargs)
        return self.CalendarTable.create(vals)

    def test_create_table_with_lines(self):
        """Crear tabla con líneas: name computado y líneas enlazadas."""
        table = self._create_table(line_ids=[
            (0, 0, {'month': 1, 'rif_digit': 0, 'day': 28}),
        ])
        self.assertEqual(table.name, f'{TEST_YEAR} — a.1 (1ra quincena)')
        self.assertEqual(len(table.line_ids), 1)
        self.assertEqual(table.line_ids.month, 1)
        self.assertEqual(table.line_ids.rif_digit, 0)
        self.assertEqual(table.line_ids.day, 28)

    def test_line_year_related_stored(self):
        """El año de la línea se hereda de la tabla y es buscable (stored)."""
        table = self._create_table()
        line = self.CalendarLine.create({
            'table_id': table.id, 'month': 2, 'rif_digit': 5, 'day': 18,
        })
        self.assertEqual(line.year, TEST_YEAR)
        found = self.CalendarLine.search([
            ('year', '=', TEST_YEAR), ('month', '=', 2), ('rif_digit', '=', 5),
        ])
        self.assertIn(line, found)

    def test_month_offset_default(self):
        """El corrimiento de mes por defecto es 'mismo mes del período'."""
        self.assertEqual(self._create_table().month_offset, '0')

    def test_unique_year_code(self):
        """No se permite repetir (year, code)."""
        self._create_table()
        with self.assertRaises(IntegrityError):
            self._create_table()

    def test_same_code_other_year_allowed(self):
        """El mismo código en otro año sí se permite."""
        self._create_table()
        next_year_table = self._create_table(year=TEST_YEAR + 1)
        self.assertTrue(next_year_table.id)

    def test_unique_table_month_digit(self):
        """No se permite repetir (table, month, digit)."""
        table = self._create_table()
        self.CalendarLine.create({
            'table_id': table.id, 'month': 1, 'rif_digit': 0, 'day': 28,
        })
        with self.assertRaises(IntegrityError):
            self.CalendarLine.create({
                'table_id': table.id, 'month': 1, 'rif_digit': 0, 'day': 30,
            })

    def test_same_month_digit_other_table_allowed(self):
        """El mismo mes/dígito en otra tabla (a.2) se permite."""
        table_a1 = self._create_table()
        table_a2 = self._create_table(code='a2')
        self.CalendarLine.create({
            'table_id': table_a1.id, 'month': 1, 'rif_digit': 0, 'day': 28,
        })
        line = self.CalendarLine.create({
            'table_id': table_a2.id, 'month': 1, 'rif_digit': 0, 'day': 15,
        })
        self.assertTrue(line.id)

    def test_cascade_delete(self):
        """Eliminar la tabla elimina sus líneas."""
        table = self._create_table(line_ids=[
            (0, 0, {'month': 1, 'rif_digit': 0, 'day': 28}),
        ])
        line_id = table.line_ids.id
        table.unlink()
        self.assertFalse(self.CalendarLine.browse(line_id).exists())


@tagged('post_install', '-at_install')
class TestSeniatCalendar2026Data(TransactionCase):
    """T2: precarga 2026 (a.1/a.2), edición persistente, vistas y menú."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CalendarTable = cls.env['l10n.ve.seniat.calendar.table']
        cls.a1 = cls.env.ref('l10n_ve_compliance_manager.seniat_calendar_2026_a1')
        cls.a2 = cls.env.ref('l10n_ve_compliance_manager.seniat_calendar_2026_a2')

    def _line(self, table, month, digit):
        line = table.line_ids.filtered(
            lambda record: record.month == month and record.rif_digit == digit
        )
        self.assertEqual(
            len(line), 1,
            f'Debe existir una única línea en {table.code}: mes {month}, dígito {digit}.',
        )
        return line

    def test_calendar_2026_tables_loaded(self):
        """RF-1/RF-2: tablas a.1 y a.2 de 2026 cargadas con 120 líneas cada una."""
        self.assertEqual(self.a1.year, 2026)
        self.assertEqual(self.a1.code, 'a1')
        self.assertEqual(self.a1.month_offset, '0')
        self.assertEqual(self.a2.year, 2026)
        self.assertEqual(self.a2.code, 'a2')
        self.assertEqual(self.a2.month_offset, '1')
        self.assertEqual(len(self.a1.line_ids), 120)
        self.assertEqual(len(self.a2.line_ids), 120)
        self.assertEqual(self._line(self.a1, 1, 0).day, 28)
        self.assertEqual(self._line(self.a2, 1, 0).day, 15)

    def test_calendar_2026_a1_matches_legacy_dict(self):
        """RF-2: a.1 replica el calendario usado hoy por el cálculo legacy."""
        legacy = self.env['l10n.ve.obligation'].SENIAT_2026_CALENDAR
        for month in range(1, 13):
            for digit in range(10):
                self.assertEqual(
                    self._line(self.a1, month, digit).day,
                    legacy[month][digit],
                    f'a.1 mes {month}, dígito {digit} no coincide con el calendario legacy.',
                )

    def test_calendar_2026_a2_spot_days(self):
        """RF-2: días destacados de a.2 (vencimiento en el mes siguiente)."""
        self.assertEqual(self._line(self.a2, 1, 3).day, 16)
        self.assertEqual(self._line(self.a2, 2, 4).day, 2)
        self.assertEqual(self._line(self.a2, 10, 9).day, 1)
        self.assertEqual(self._line(self.a2, 12, 1).day, 15)

    def test_calendar_edit_persists_across_upgrade(self):
        """RF-3: una edición del contador sobrevive a una actualización del módulo."""
        line = self._line(self.a1, 1, 0)
        self.assertEqual(line.day, 28)
        line.day = 5
        convert.convert_file(
            self.env,
            'l10n_ve_compliance_manager',
            'data/seniat_calendar_2026.xml',
            None,
            mode='update',
        )
        line.invalidate_recordset()
        self.assertEqual(line.day, 5, 'noupdate="1": la actualización no debe pisar la edición.')

    def test_calendar_views_exist(self):
        """Existen las vistas list/form/search de la tabla del calendario."""
        views = {
            'view_l10n_ve_seniat_calendar_table_list': (
                'list', ['year', 'code', 'month_offset'],
            ),
            'view_l10n_ve_seniat_calendar_table_form': (
                'form', ['year', 'code', 'month_offset', 'line_ids', 'rif_digit', 'day'],
            ),
            'view_l10n_ve_seniat_calendar_table_search': (
                'search', ['year', 'code'],
            ),
        }
        for xmlid, (view_type, field_names) in views.items():
            view = self.env.ref(f'l10n_ve_compliance_manager.{xmlid}')
            self.assertEqual(view.type, view_type)
            self.assertEqual(view.model, 'l10n.ve.seniat.calendar.table')
            for field_name in field_names:
                self.assertIn(f'name="{field_name}"', view.arch)

    def test_seniat_calendar_action_and_menu(self):
        """Existe la acción y el menú "Calendario SENIAT" bajo Configuración."""
        action = self.env.ref('l10n_ve_compliance_manager.action_l10n_ve_seniat_calendar')
        self.assertEqual(action.res_model, 'l10n.ve.seniat.calendar.table')
        self.assertEqual(action.view_mode, 'list,form')
        menu = self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_seniat_calendar')
        self.assertEqual(menu.name, 'Calendario SENIAT')
        self.assertEqual(
            menu.parent_id,
            self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_compliance_config'),
        )
        self.assertEqual(menu.action, action)


@tagged('post_install', '-at_install')
class TestIslrCalendar2026Data(TransactionCase):
    """T1 spec 004: precarga de referencia de las tablas de ISLR 2026."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.est_islr = cls.env.ref('l10n_ve_compliance_manager.seniat_calendar_2026_est_islr')
        cls.ret_islr = cls.env.ref('l10n_ve_compliance_manager.seniat_calendar_2026_ret_islr')

    def _line(self, table, month, digit):
        line = table.line_ids.filtered(
            lambda record: record.month == month and record.rif_digit == digit
        )
        self.assertEqual(
            len(line), 1,
            f'Debe existir una única línea en {table.code}: mes {month}, dígito {digit}.',
        )
        return line

    def test_islr_calendar_2026_tables_loaded(self):
        """RF-1/RF-2: tablas est_islr y ret_islr 2026 con su corrimiento de mes."""
        self.assertEqual(self.est_islr.year, 2026)
        self.assertEqual(self.est_islr.code, 'est_islr')
        self.assertEqual(self.est_islr.month_offset, '0')
        self.assertEqual(self.ret_islr.year, 2026)
        self.assertEqual(self.ret_islr.code, 'ret_islr')
        self.assertEqual(self.ret_islr.month_offset, '1')

    def test_islr_calendar_2026_line_counts(self):
        """RF-2: est_islr 30 líneas (jun, sep, dic) y ret_islr 120 (12 meses)."""
        self.assertEqual(len(self.est_islr.line_ids), 30)
        self.assertEqual(len(self.ret_islr.line_ids), 120)
        self.assertEqual(set(self.est_islr.line_ids.mapped('month')), {6, 9, 12})
        self.assertEqual(set(self.ret_islr.line_ids.mapped('month')), set(range(1, 13)))

    def test_islr_calendar_reference_day_pattern(self):
        """RF-2/RF-3: patrón de referencia día = último dígito del RIF + 10."""
        for table in (self.est_islr, self.ret_islr):
            for line in table.line_ids:
                self.assertEqual(
                    line.day, line.rif_digit + 10,
                    f'{table.code}: mes {line.month}, dígito {line.rif_digit} '
                    f'debe usar el día de referencia {line.rif_digit + 10}.',
                )
        self.assertEqual(self._line(self.est_islr, 6, 0).day, 10)
        self.assertEqual(self._line(self.est_islr, 12, 9).day, 19)
        self.assertEqual(self._line(self.ret_islr, 1, 4).day, 14)

    def test_islr_calendar_marked_as_reference(self):
        """RF-3: las tablas quedan marcadas como referencia sujeta a verificación."""
        for table in (self.est_islr, self.ret_islr):
            description = (table.description or '').lower()
            self.assertIn('referencia', description)
            self.assertIn('verificación', description)

    def test_islr_calendar_edit_persists_across_upgrade(self):
        """RF-3: la corrección del contador sobrevive a una actualización del módulo."""
        line = self._line(self.ret_islr, 1, 0)
        self.assertEqual(line.day, 10)
        line.day = 3
        convert.convert_file(
            self.env,
            'l10n_ve_compliance_manager',
            'data/islr_calendar_2026.xml',
            None,
            mode='update',
        )
        line.invalidate_recordset()
        self.assertEqual(line.day, 3, 'noupdate="1": la actualización no debe pisar la edición.')


@tagged('post_install', '-at_install')
class TestBankHolidayModel(TransactionCase):
    """T3: modelo de feriados bancarios (fecha única + año computado)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BankHoliday = cls.env['l10n.ve.bank.holiday']

    def test_create_holiday_computes_year(self):
        """RF-19: al crear un feriado el año se computa desde la fecha y es buscable."""
        holiday = self.BankHoliday.create({
            'name': 'Día de prueba',
            'date': fields.Date.to_date(f'{TEST_YEAR}-03-15'),
        })
        self.assertEqual(holiday.year, TEST_YEAR)
        found = self.BankHoliday.search([
            ('year', '=', TEST_YEAR),
            ('date', '=', fields.Date.to_date(f'{TEST_YEAR}-03-15')),
        ])
        self.assertIn(holiday, found)

    def test_unique_date(self):
        """RF-19: no se permite repetir la fecha de un feriado (UNIQUE(date))."""
        self.BankHoliday.create({
            'name': 'Feriado uno',
            'date': fields.Date.to_date(f'{TEST_YEAR}-04-01'),
        })
        with self.assertRaises(IntegrityError):
            self.BankHoliday.create({
                'name': 'Feriado dos',
                'date': fields.Date.to_date(f'{TEST_YEAR}-04-01'),
            })

    def test_future_year_holiday_creatable(self):
        """RF-19: se puede cargar un feriado de un año futuro desde la interfaz."""
        holiday = self.BankHoliday.create({
            'name': 'Feriado futuro',
            'date': fields.Date.to_date(f'{TEST_YEAR + 1}-05-01'),
        })
        self.assertEqual(holiday.year, TEST_YEAR + 1)


@tagged('post_install', '-at_install')
class TestBankHoliday2026Data(TransactionCase):
    """T3: precarga de feriados bancarios 2026, vistas y menú."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BankHoliday = cls.env['l10n.ve.bank.holiday']

    def test_bank_holidays_2026_loaded(self):
        """RF-19: precarga 2026 completa, sin duplicados y con año computado."""
        holidays = self.BankHoliday.search([('year', '=', 2026)])
        self.assertEqual(len(holidays), 13)
        dates = holidays.mapped('date')
        self.assertEqual(len(dates), len(set(dates)), 'No debe haber fechas duplicadas.')
        expected = {
            'bank_holiday_2026_01_01': ('Año Nuevo', '2026-01-01'),
            'bank_holiday_2026_02_16': ('Lunes de Carnaval', '2026-02-16'),
            'bank_holiday_2026_04_03': ('Viernes Santo', '2026-04-03'),
            'bank_holiday_2026_12_25': ('Navidad', '2026-12-25'),
        }
        for xmlid, (name, date_str) in expected.items():
            holiday = self.env.ref(f'l10n_ve_compliance_manager.{xmlid}')
            self.assertEqual(holiday.name, name)
            self.assertEqual(holiday.date, fields.Date.to_date(date_str))
            self.assertEqual(holiday.year, 2026)

    def test_bank_holiday_views_exist(self):
        """Existen las vistas list/form/search de feriados bancarios."""
        views = {
            'view_l10n_ve_bank_holiday_list': ('list', ['name', 'date', 'year']),
            'view_l10n_ve_bank_holiday_form': ('form', ['name', 'date', 'year']),
            'view_l10n_ve_bank_holiday_search': ('search', ['name', 'date', 'year']),
        }
        for xmlid, (view_type, field_names) in views.items():
            view = self.env.ref(f'l10n_ve_compliance_manager.{xmlid}')
            self.assertEqual(view.type, view_type)
            self.assertEqual(view.model, 'l10n.ve.bank.holiday')
            for field_name in field_names:
                self.assertIn(f'name="{field_name}"', view.arch)

    def test_bank_holiday_action_and_menu(self):
        """Existe la acción y el menú "Feriados bancarios" bajo Configuración."""
        action = self.env.ref('l10n_ve_compliance_manager.action_l10n_ve_bank_holiday')
        self.assertEqual(action.res_model, 'l10n.ve.bank.holiday')
        self.assertEqual(action.view_mode, 'list,form')
        menu = self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_bank_holidays')
        self.assertEqual(menu.name, 'Feriados bancarios')
        self.assertEqual(
            menu.parent_id,
            self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_compliance_config'),
        )
        self.assertEqual(menu.action, action)


@tagged('post_install', '-at_install')
class TestObligationTypeSeniatConfig(TransactionCase):
    """T4: campos de configuración SENIAT en l10n.ve.obligation.type (RF-5)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ObligationType = cls.env['l10n.ve.obligation.type']

    def test_seniat_defaults(self):
        """RF-5: por defecto el tipo no usa calendario ni copia al cliente."""
        otype = self.ObligationType.create({'name': 'Tipo base T4'})
        self.assertEqual(otype.seniat_table_code, 'none')
        self.assertFalse(otype.alert_cc_client)

    def test_quincenal_with_seniat_table_saves(self):
        """RF-5: un IVA quincenal con tabla a.1 guarda sin error (criterio T4)."""
        otype = self.ObligationType.create({
            'name': 'IVA Quincenal T4',
            'tax_type': 'iva',
            'periodicity': 'quincenal',
            'seniat_table_code': 'a1',
        })
        self.assertEqual(otype.periodicity, 'quincenal')
        self.assertEqual(otype.seniat_table_code, 'a1')

    def test_seniat_table_code_matches_calendar_codes(self):
        """RF-5: los códigos de tabla del tipo coinciden con los del calendario."""
        selection = dict(self.ObligationType._fields['seniat_table_code'].selection)
        self.assertEqual(set(selection), {'none', 'a1', 'a2', 'est_islr', 'ret_islr'})
        calendar_selection = dict(
            self.env['l10n.ve.seniat.calendar.table']._fields['code'].selection
        )
        for code in ('a1', 'a2', 'est_islr', 'ret_islr'):
            self.assertIn(code, calendar_selection)

    def test_alert_cc_client_toggle(self):
        """RF-15: la copia al cliente se activa por tipo de obligación."""
        otype = self.ObligationType.create({
            'name': 'Tipo CC T4',
            'alert_cc_client': True,
        })
        self.assertTrue(otype.alert_cc_client)


@tagged('post_install', '-at_install')
class TestComplianceClientSeniatConfig(TransactionCase):
    """T4: campos de configuración SENIAT en l10n.ve.compliance.client (RF-5)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Client = cls.env['l10n.ve.compliance.client']
        cls.ObligationType = cls.env['l10n.ve.obligation.type']
        cls.partner = cls.env['res.partner'].create({'name': 'Partner T4'})

    def _create_client(self, **kwargs):
        vals = {
            'name': 'Cliente T4',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
        }
        vals.update(kwargs)
        return self.Client.create(vals)

    def test_seniat_defaults(self):
        """RF-5: por defecto el cliente no es SPE y no tiene tipos asignados."""
        client = self._create_client()
        self.assertFalse(client.is_spe)
        self.assertFalse(client.applicable_type_ids)

    def test_spe_toggle(self):
        """RF-5: el cliente se puede marcar como Sujeto Pasivo Especial."""
        self.assertTrue(self._create_client(is_spe=True).is_spe)

    def test_assign_applicable_types(self):
        """RF-12: el cliente recibe los tipos que la generación usaría."""
        client = self._create_client()
        otype_iva = self.ObligationType.create({
            'name': 'IVA Quincenal cliente T4',
            'periodicity': 'quincenal',
            'seniat_table_code': 'a1',
        })
        otype_islr = self.ObligationType.create({
            'name': 'ISLR cliente T4',
            'periodicity': 'monthly',
        })
        client.applicable_type_ids = [(6, 0, [otype_iva.id, otype_islr.id])]
        self.assertEqual(client.applicable_type_ids, otype_iva | otype_islr)

    def test_applicable_types_are_per_client(self):
        """RF-12: los tipos aplicables son independientes entre clientes."""
        client_a = self._create_client()
        client_b = self._create_client()
        otype = self.ObligationType.create({'name': 'Tipo compartido T4'})
        client_a.applicable_type_ids = [(6, 0, otype.ids)]
        self.assertEqual(client_a.applicable_type_ids, otype)
        self.assertFalse(client_b.applicable_type_ids)


@tagged('post_install', '-at_install')
class TestSeniatConfigViews(TransactionCase):
    """T4: las vistas exponen los campos de configuración SENIAT (RF-5)."""

    def _assert_fields_in_view(self, xmlid, model, field_names):
        view = self.env.ref(f'l10n_ve_compliance_manager.{xmlid}')
        self.assertEqual(view.model, model)
        for field_name in field_names:
            self.assertIn(f'name="{field_name}"', view.arch)

    def test_client_form_shows_fiscal_config(self):
        """La pestaña de configuración fiscal muestra SPE y tipos aplicables."""
        self._assert_fields_in_view(
            'view_l10n_ve_compliance_client_form',
            'l10n.ve.compliance.client',
            ['is_spe', 'applicable_type_ids'],
        )

    def test_client_search_has_spe_filter(self):
        """Existe el filtro SPE en la búsqueda de clientes."""
        view = self.env.ref('l10n_ve_compliance_manager.view_l10n_ve_compliance_client_search')
        self.assertIn("('is_spe', '=', True)", view.arch)

    def test_obligation_type_form_shows_seniat_config(self):
        """El formulario del tipo muestra tabla SENIAT y copia al cliente."""
        self._assert_fields_in_view(
            'view_l10n_ve_obligation_type_form',
            'l10n.ve.obligation.type',
            ['seniat_table_code', 'alert_cc_client'],
        )

    def test_obligation_type_list_shows_seniat_table_code(self):
        """La lista de tipos expone la tabla SENIAT."""
        self._assert_fields_in_view(
            'view_l10n_ve_obligation_type_list',
            'l10n.ve.obligation.type',
            ['seniat_table_code'],
        )


@tagged('post_install', '-at_install')
class TestObligationDueDateCalculation(TransactionCase):
    """T5: cálculo de vencimientos con calendario SENIAT, quincenas y corrimiento a día hábil."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.ObligationType = cls.env['l10n.ve.obligation.type']
        cls.partner = cls.env['res.partner'].create({'name': 'Partner T5'})

    def _create_client(self, rif, is_spe=True):
        return self.env['l10n.ve.compliance.client'].create({
            'name': f'Cliente T5 {rif}',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': rif,
            'is_spe': is_spe,
        })

    def _create_type(self, **kwargs):
        vals = {
            'name': 'IVA Quincenal T5',
            'periodicity': 'quincenal',
            'seniat_table_code': 'a1',
        }
        vals.update(kwargs)
        return self.ObligationType.create(vals)

    def _create_obligation(self, client, obligation_type, period, quincena='monthly'):
        return self.Obligation.create({
            'name': f'OBL-T5-{period}-{quincena}',
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
            'period': period,
            'quincena': quincena,
        })

    def test_spe_q1_exact_calendar_days(self):
        """RF-6/RF-10: SPE usa la tabla a.1 del mes del período (dígitos 0, 5 y 9)."""
        obligation_type = self._create_type()
        expected = {
            'J-00000000-0': '2026-01-28',
            'J-00000005-5': '2026-01-22',
            'J-00000009-9': '2026-01-29',
        }
        for rif, due_date in expected.items():
            obligation = self._create_obligation(
                self._create_client(rif), obligation_type, '01/2026', 'q1',
            )
            self.assertEqual(
                obligation.due_date,
                fields.Date.to_date(due_date),
                f'SPE {rif} q1 01/2026 debe vencer el {due_date}.',
            )

    def test_spe_q2_exact_calendar_days(self):
        """RF-6/RF-11: q2 usa a.2 del mes, cae en el mes siguiente y se corre a día hábil."""
        obligation_type = self._create_type()
        expected = {
            'J-00000000-0': '2026-02-18',
            'J-00000005-5': '2026-02-05',
            'J-00000009-9': '2026-02-18',
        }
        for rif, due_date in expected.items():
            obligation = self._create_obligation(
                self._create_client(rif), obligation_type, '01/2026', 'q2',
            )
            self.assertEqual(
                obligation.due_date,
                fields.Date.to_date(due_date),
                f'SPE {rif} q2 01/2026 debe vencer el {due_date}.',
            )

    def test_spe_q2_crosses_year(self):
        """RF-11: la segunda quincena de diciembre vence en enero del año siguiente."""
        obligation = self._create_obligation(
            self._create_client('J-00000000-0'), self._create_type(), '12/2026', 'q2',
        )
        self.assertEqual(obligation.due_date, fields.Date.to_date('2027-01-04'))

    def test_spe_q2_shifts_weekday_holiday_to_monday(self):
        """RF-20: un vencimiento que cae en feriado entre semana se corre al lunes siguiente."""
        obligation = self._create_obligation(
            self._create_client('J-00000000-0'), self._create_type(), '04/2026', 'q2',
        )
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-05-04'))

    def test_no_spe_uses_day_15_of_next_month(self):
        """RF-7: el cliente no-SPE vence el día 15 del mes siguiente al período."""
        obligation_type = self._create_type(periodicity='monthly')
        client = self._create_client('J-00000000-0', is_spe=False)
        shifted = self._create_obligation(client, obligation_type, '01/2026')
        self.assertEqual(shifted.due_date, fields.Date.to_date('2026-02-18'))
        banking = self._create_obligation(client, obligation_type, '05/2026')
        self.assertEqual(banking.due_date, fields.Date.to_date('2026-06-15'))

    def test_spe_without_rif_has_no_due_date(self):
        """RF-8: sin dígitos en el RIF no se calcula vencimiento por calendario."""
        obligation = self._create_obligation(
            self._create_client('J--'), self._create_type(), '01/2026', 'q1',
        )
        self.assertFalse(obligation.due_date)

    def test_manual_due_date_is_not_shifted(self):
        """RF-20: la fecha fijada manualmente por el contador no se corrige."""
        obligation = self._create_obligation(
            self._create_client('J-00000000-0'), self._create_type(), '01/2026', 'q1',
        )
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-28'))
        obligation.due_date = fields.Date.to_date('2026-02-15')
        self.assertTrue(obligation.due_date_override)
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-02-15'))

    def test_shift_to_monday_without_holidays(self):
        """RF-19/RF-20: sin feriados cargados el corrimiento solo evita fines de semana."""
        table = self.env['l10n.ve.seniat.calendar.table'].create({
            'year': TEST_YEAR,
            'code': 'a1',
            'month_offset': '0',
        })
        self.env['l10n.ve.seniat.calendar'].create({
            'table_id': table.id,
            'month': 1,
            'rif_digit': 0,
            'day': 4,
        })
        obligation = self._create_obligation(
            self._create_client('J-00000000-0'),
            self._create_type(),
            f'01/{TEST_YEAR}',
            'q1',
        )
        self.assertEqual(obligation.due_date, fields.Date.to_date(f'{TEST_YEAR}-01-05'))

    def test_is_banking_day_weekends_and_holidays(self):
        """RF-19/RF-20: fines de semana y feriados cargados no son días hábiles."""
        to_date = fields.Date.to_date
        self.assertFalse(self.Obligation._is_banking_day(to_date('2026-01-03')))
        self.assertFalse(self.Obligation._is_banking_day(to_date('2026-01-04')))
        self.assertFalse(self.Obligation._is_banking_day(to_date('2026-01-01')))
        self.assertFalse(self.Obligation._is_banking_day(to_date('2026-05-01')))
        self.assertTrue(self.Obligation._is_banking_day(to_date('2026-01-28')))
        self.assertTrue(self.Obligation._is_banking_day(to_date('2099-01-02')))

    def test_shift_to_next_banking_day(self):
        """RF-20: el corrimiento avanza hasta el siguiente día hábil bancario."""
        to_date = fields.Date.to_date
        self.assertEqual(
            self.Obligation._shift_to_next_banking_day(to_date('2026-02-15')),
            to_date('2026-02-18'),
        )
        self.assertEqual(
            self.Obligation._shift_to_next_banking_day(to_date('2026-01-28')),
            to_date('2026-01-28'),
        )


@tagged('post_install', '-at_install')
class TestObligationGeneration(TransactionCase):
    """T6: generación automática, idempotencia y alerta de calendario faltante."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.ObligationType = cls.env['l10n.ve.obligation.type']
        cls.Client = cls.env['l10n.ve.compliance.client']
        cls.Alert = cls.env['l10n.ve.alert']
        cls.partner = cls.env['res.partner'].create({'name': 'Partner T6'})
        cls.accountant = cls.env['res.users'].create({
            'name': 'Contador T6',
            'login': 'contador_t6',
            'email': 'contador.t6@example.com',
        })

    def _create_client(self, rif='J-00000000-0', is_spe=True, **kwargs):
        vals = {
            'name': f'Cliente T6 {rif}',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': rif,
            'is_spe': is_spe,
        }
        vals.update(kwargs)
        return self.Client.create(vals)

    def _create_type(self, **kwargs):
        vals = {
            'name': 'IVA Quincenal T6',
            'periodicity': 'quincenal',
            'seniat_table_code': 'a1',
        }
        vals.update(kwargs)
        return self.ObligationType.create(vals)

    def _search_obligations(self, client, obligation_type, period=None, quincena=None):
        domain = [
            ('client_id', '=', client.id),
            ('obligation_type_id', '=', obligation_type.id),
        ]
        if period:
            domain.append(('period', '=', period))
        if quincena:
            domain.append(('quincena', '=', quincena))
        return self.Obligation.search(domain)

    def _current_window_periods(self):
        today = fields.Date.today()
        next_month = today.month % 12 + 1
        next_year = today.year + (today.month == 12)
        return [
            f'{today.month:02d}/{today.year}',
            f'{next_month:02d}/{next_year}',
        ]

    def _calendar_missing_alerts(self, client):
        return self.Alert.search([
            ('client_id', '=', client.id),
            ('alert_type', '=', 'calendar_missing'),
        ])

    def test_cron_generates_quincenas_and_rest_of_types(self):
        """RF-12: un cliente SPE genera 2 quincenas por mes y el resto de sus tipos."""
        quincenal = self._create_type()
        mensual = self._create_type(
            name='ISLR Mensual T6',
            periodicity='monthly',
            seniat_table_code='none',
            due_day_rule='dia_fijo',
            due_day_value=15,
        )
        client = self._create_client(
            applicable_type_ids=[(6, 0, (quincenal + mensual).ids)],
        )
        self.Obligation._cron_generate_obligations()
        for period in self._current_window_periods():
            q1 = self._search_obligations(client, quincenal, period, 'q1')
            q2 = self._search_obligations(client, quincenal, period, 'q2')
            self.assertEqual(len(q1), 1)
            self.assertEqual(len(q2), 1)
            monthly = self._search_obligations(client, mensual, period, 'monthly')
            self.assertEqual(len(monthly), 1)
            self.assertTrue(monthly.due_date)
        self.assertTrue(
            all(self._search_obligations(client, quincenal).mapped('due_date')),
            'Las quincenas del calendario 2026 deben tener vencimiento calculado.',
        )
        self.assertFalse(self._calendar_missing_alerts(client))

    def test_cron_non_spe_generates_monthly_day_15(self):
        """RF-7/RF-12: el cliente no-SPE genera la obligación mensual y no quincenas."""
        quincenal = self._create_type()
        mensual = self._create_type(
            name='IVA Mensual no-SPE T6',
            periodicity='monthly',
            seniat_table_code='a1',
        )
        client = self._create_client(
            is_spe=False,
            applicable_type_ids=[(6, 0, (quincenal + mensual).ids)],
        )
        self.Obligation._cron_generate_obligations()
        for period in self._current_window_periods():
            monthly = self._search_obligations(client, mensual, period, 'monthly')
            self.assertEqual(len(monthly), 1)
            self.assertTrue(monthly.due_date)
            self.assertFalse(self._search_obligations(client, quincenal, period, 'q1'))
            self.assertFalse(self._search_obligations(client, quincenal, period, 'q2'))

    def test_cron_is_idempotent(self):
        """RF-13: correr la generación dos veces no duplica obligaciones."""
        quincenal = self._create_type()
        client = self._create_client(applicable_type_ids=quincenal.ids)
        self.Obligation._cron_generate_obligations()
        self.Obligation._cron_generate_obligations()
        for period in self._current_window_periods():
            for quincena in ('q1', 'q2'):
                self.assertEqual(
                    len(self._search_obligations(client, quincenal, period, quincena)),
                    1,
                    f'{period} {quincena} debe existir exactamente una vez.',
                )
        self.assertEqual(len(self._search_obligations(client, quincenal)), 4)

    def test_generate_for_missing_calendar_year_alerts_once(self):
        """RF-4: sin calendario cargado no se generan obligaciones y se alerta al contador una vez."""
        quincenal = self._create_type()
        client = self._create_client(
            accountant_id=self.accountant.id,
            applicable_type_ids=quincenal.ids,
        )
        for month in (1, 2):
            self.Obligation._generate_for_client(client, TEST_YEAR, month)
        self.assertFalse(self.Obligation.search([
            ('client_id', '=', client.id),
            ('period', 'ilike', f'/{TEST_YEAR}'),
        ]))
        alerts = self._calendar_missing_alerts(client)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.state, 'pending')
        self.assertIn(str(TEST_YEAR), alerts.name)
        self.assertEqual(alerts.recipient_ids, self.accountant.partner_id)
        for month in (1, 2):
            self.Obligation._generate_for_client(client, TEST_YEAR, month)
        self.assertEqual(len(self._calendar_missing_alerts(client)), 1)

    def test_action_generate_obligations_button(self):
        """RF-12: el botón manual genera el mes actual y el próximo para su cliente."""
        quincenal = self._create_type()
        client = self._create_client(applicable_type_ids=quincenal.ids)
        other_client = self._create_client(
            rif='J-00000001-1',
            applicable_type_ids=quincenal.ids,
        )
        client.action_generate_obligations()
        self.assertEqual(len(self._search_obligations(client, quincenal)), 4)
        self.assertFalse(self._search_obligations(other_client, quincenal))
        view = self.env.ref('l10n_ve_compliance_manager.view_l10n_ve_compliance_client_form')
        self.assertIn('action_generate_obligations', view.arch)

    def test_cron_record_registered(self):
        """El cron queda registrado y llama a la generación automática."""
        cron = self.env.ref(
            'l10n_ve_compliance_manager.cron_l10n_ve_generate_obligations'
        )
        self.assertTrue(cron.active)
        self.assertEqual(cron.model_id.model, 'l10n.ve.obligation')
        self.assertIn('_cron_generate_obligations', cron.code)

    def test_alert_type_calendar_missing_available(self):
        """RF-4: el tipo de alerta 'calendar_missing' existe en el modelo de alertas."""
        selection = dict(self.Alert._fields['alert_type'].selection)
        self.assertIn('calendar_missing', selection)
        self.assertEqual(
            self.Obligation.ALERT_TYPE_LABELS['calendar_missing'],
            'Calendario faltante',
        )


@tagged('post_install', '-at_install')
class TestAlertNotifications(TransactionCase):
    """T7: alertas al contador — destinatario, CC opcional, email real y WhatsApp
    (RF-14, RF-15, RF-16)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.ObligationType = cls.env['l10n.ve.obligation.type']
        cls.Alert = cls.env['l10n.ve.alert']
        cls.Mail = cls.env['mail.mail']
        cls.accountant = cls.env['res.users'].create({
            'name': 'Contador T7',
            'login': 'contador_t7',
            'email': 'contador.t7@example.com',
        })
        cls.accountant.partner_id.phone = '+58 414-1234567'
        cls.client_partner = cls.env['res.partner'].create({
            'name': 'Cliente T7 Contacto',
            'email': 'cliente.t7@example.com',
            'phone': '+58 212-5555555',
        })
        cls.today = fields.Date.today()

    def _create_client(self, **kwargs):
        vals = {
            'name': 'Cliente T7',
            'partner_id': self.client_partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-00000000-0',
            'accountant_id': self.accountant.id,
        }
        vals.update(kwargs)
        return self.env['l10n.ve.compliance.client'].create(vals)

    def _create_type(self, **kwargs):
        vals = {
            'name': 'IVA T7',
            'alert_enabled': True,
            'alert_days_before': 5,
            'alert_channel': 'email',
        }
        vals.update(kwargs)
        return self.ObligationType.create(vals)

    def _create_due_soon_obligation(self, client, obligation_type):
        obligation = self.Obligation.create({
            'name': f'OBL-T7-{obligation_type.name}',
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
        })
        obligation.due_date = self.today + timedelta(days=3)
        return obligation

    def _alerts_for(self, obligation, alert_type='due_soon', channel=None):
        domain = [
            ('obligation_id', '=', obligation.id),
            ('alert_type', '=', alert_type),
        ]
        if channel:
            domain.append(('channel', '=', channel))
        return self.Alert.search(domain)

    def test_alert_recipients_accountant(self):
        """RF-14: el destinatario principal es el partner del contador asignado."""
        client = self._create_client()
        obligation_type = self._create_type()
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.recipient_ids, self.accountant.partner_id)

    def test_alert_recipients_cc_client(self):
        """RF-15: con alert_cc_client se agrega el contacto del cliente como destinatario."""
        client = self._create_client()
        obligation_type = self._create_type(alert_cc_client=True)
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(
            alerts.recipient_ids,
            self.accountant.partner_id | self.client_partner,
        )

    def test_alert_recipients_no_accountant(self):
        """RF-14: sin contador la alerta se crea sin destinatarios y queda pendiente."""
        client = self._create_client(accountant_id=False)
        obligation_type = self._create_type()
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation)
        self.assertEqual(len(alerts), 1)
        self.assertFalse(alerts.recipient_ids)
        self.assertEqual(alerts.state, 'pending')

    def test_alert_email_sent(self):
        """RF-16: el email crea un mail.mail para los destinatarios y marca la alerta enviada."""
        client = self._create_client()
        obligation_type = self._create_type(alert_cc_client=True)
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation, channel='email')
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.state, 'sent')
        self.assertTrue(alerts.sent_date)
        mails = self.Mail.search([
            ('model', '=', 'l10n.ve.alert'),
            ('res_id', '=', alerts.id),
        ])
        self.assertEqual(len(mails), 1)
        self.assertEqual(
            mails.recipient_ids,
            self.accountant.partner_id | self.client_partner,
        )
        self.assertEqual(mails.state, 'outgoing')
        self.assertIn('obligación por vencer', mails.body)

    def test_alert_email_without_recipient_email_stays_pending(self):
        """RF-16: contador sin email → la alerta queda pendiente y el cron no falla."""
        accountant = self.env['res.users'].create({
            'name': 'Contador T7 Sin Email',
            'login': 'contador_t7_sin_email',
        })
        accountant.partner_id.email = False
        client = self._create_client(accountant_id=accountant.id)
        obligation_type = self._create_type()
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation, channel='email')
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.state, 'pending')
        self.assertFalse(alerts.sent_date)
        self.assertFalse(self.Mail.search([
            ('model', '=', 'l10n.ve.alert'),
            ('res_id', '=', alerts.id),
        ]))

    def test_alert_whatsapp_link_uses_accountant_phone(self):
        """RF-16: el link wa.me usa el teléfono del contador aunque el cliente vaya en copia."""
        client = self._create_client()
        obligation_type = self._create_type(
            alert_cc_client=True, alert_channel='whatsapp',
        )
        obligation = self._create_due_soon_obligation(client, obligation_type)

        self.Obligation._cron_generate_compliance_alerts()

        alerts = self._alerts_for(obligation, channel='whatsapp')
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.state, 'sent')
        url = alerts.get_wa_url(self.accountant.partner_id.id)
        self.assertTrue(url.startswith('https://wa.me/584141234567?text='))
        self.assertIn(url, alerts.message)
        self.assertNotIn('582125555555', alerts.message)

    def test_template_body_clear_for_accountant(self):
        """RF-16: la plantilla explica en claro la obligación por vencer y el calendario faltante."""
        template = self.env.ref('l10n_ve_compliance_manager.email_template_l10n_ve_alert')
        self.assertEqual(template.model, 'l10n.ve.alert')
        client = self._create_client()
        obligation = self._create_due_soon_obligation(client, self._create_type())
        due_soon_alert = self.Alert.create({
            'name': 'Alerta T7 vence pronto',
            'client_id': client.id,
            'obligation_id': obligation.id,
            'alert_type': 'due_soon',
            'date': fields.Datetime.now(),
            'channel': 'email',
            'recipient_ids': [(6, 0, self.accountant.partner_id.ids)],
            'message': 'Mensaje de prueba',
        })
        body = template._render_field('body_html', due_soon_alert.ids)[due_soon_alert.id]
        self.assertIn('obligación por vencer', body)

        calendar_alert = self.Alert.create({
            'name': 'Alerta T7 calendario faltante',
            'client_id': client.id,
            'alert_type': 'calendar_missing',
            'date': fields.Datetime.now(),
            'channel': 'email',
            'recipient_ids': [(6, 0, self.accountant.partner_id.ids)],
            'message': 'Mensaje de prueba',
        })
        body = template._render_field('body_html', calendar_alert.ids)[calendar_alert.id]
        self.assertIn('Falta el calendario', body)


@tagged('post_install', '-at_install')
class TestAccountantRecordRules(TransactionCase):
    """T8: seguridad por contador — reglas de registro (RF-17)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Client = cls.env['l10n.ve.compliance.client']
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.accountant_group = cls.env.ref('account.group_account_user')
        cls.compliance_group = cls.env.ref(
            'l10n_ve_compliance_manager.l10n_ve_compliance_accountant'
        )
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.partner = cls.env['res.partner'].create({'name': 'Partner T8'})
        cls.contador_a = cls.env['res.users'].create({
            'name': 'Contador A T8',
            'login': 'contador_a_t8',
            'group_ids': [(6, 0, cls.accountant_group.ids)],
        })
        cls.contador_b = cls.env['res.users'].create({
            'name': 'Contador B T8',
            'login': 'contador_b_t8',
            'group_ids': [(6, 0, (cls.accountant_group | cls.compliance_group).ids)],
        })
        cls.client_a = cls._create_client('Cliente A T8', cls.contador_a)
        cls.client_b = cls._create_client('Cliente B T8', cls.contador_b)
        cls.client_no_accountant = cls._create_client('Cliente sin contador T8', None)
        cls.obligation_a = cls._create_obligation(cls.client_a, 'OBL-A-T8')
        cls.obligation_b = cls._create_obligation(cls.client_b, 'OBL-B-T8')
        cls.obligation_no_accountant = cls._create_obligation(
            cls.client_no_accountant, 'OBL-N-T8'
        )

    @classmethod
    def _create_client(cls, name, accountant):
        return cls.Client.create({
            'name': name,
            'partner_id': cls.partner.id,
            'company_id': cls.env.company.id,
            'accountant_id': accountant.id if accountant else False,
        })

    @classmethod
    def _create_obligation(cls, client, name):
        return cls.Obligation.create({
            'name': name,
            'client_id': client.id,
        })

    def _all_client_ids(self):
        return (self.client_a + self.client_b + self.client_no_accountant).ids

    def _all_obligation_ids(self):
        return (
            self.obligation_a + self.obligation_b + self.obligation_no_accountant
        ).ids

    def test_rules_loaded_with_expected_domains(self):
        """RF-17: reglas de registro por contador y allow-all para el admin."""
        obligation_rule = self.env.ref(
            'l10n_ve_compliance_manager.rule_l10n_ve_obligation_accountant'
        )
        self.assertEqual(obligation_rule.model_id.model, 'l10n.ve.obligation')
        self.assertEqual(
            obligation_rule.domain_force,
            "[('client_id.accountant_id', '=', user.id)]",
        )
        self.assertIn(self.accountant_group, obligation_rule.groups)
        self.assertIn(self.compliance_group, obligation_rule.groups)
        client_rule = self.env.ref(
            'l10n_ve_compliance_manager.rule_l10n_ve_compliance_client_accountant'
        )
        self.assertEqual(client_rule.model_id.model, 'l10n.ve.compliance.client')
        self.assertEqual(client_rule.domain_force, "[('accountant_id', '=', user.id)]")
        admin_rule = self.env.ref(
            'l10n_ve_compliance_manager.rule_l10n_ve_obligation_admin'
        )
        self.assertEqual(admin_rule.domain_force, "[(1, '=', 1)]")
        self.assertIn(self.env.ref('base.group_system'), admin_rule.groups)

    def test_obligation_isolation_between_accountants(self):
        """RF-17: un contador no ve las obligaciones del otro contador."""
        visible_to_a = self.Obligation.with_user(self.contador_a).search([
            ('id', 'in', self._all_obligation_ids()),
        ])
        self.assertIn(self.obligation_a, visible_to_a)
        self.assertNotIn(self.obligation_b, visible_to_a)
        self.assertNotIn(self.obligation_no_accountant, visible_to_a)
        visible_to_b = self.Obligation.with_user(self.contador_b).search([
            ('id', 'in', self._all_obligation_ids()),
        ])
        self.assertIn(self.obligation_b, visible_to_b)
        self.assertNotIn(self.obligation_a, visible_to_b)
        self.assertNotIn(self.obligation_no_accountant, visible_to_b)

    def test_client_isolation_between_accountants(self):
        """RF-17: cada contador solo ve los clientes donde figura asignado."""
        visible_to_a = self.Client.with_user(self.contador_a).search([
            ('id', 'in', self._all_client_ids()),
        ])
        self.assertEqual(visible_to_a.ids, [self.client_a.id])
        visible_to_b = self.Client.with_user(self.contador_b).search([
            ('id', 'in', self._all_client_ids()),
        ])
        self.assertEqual(visible_to_b.ids, [self.client_b.id])

    def test_client_without_accountant_only_visible_to_admin(self):
        """RF-17: el cliente sin contador no lo ve ningún contador y el admin sí."""
        client_domain = [('id', '=', self.client_no_accountant.id)]
        self.assertFalse(self.Client.with_user(self.contador_a).search(client_domain))
        self.assertTrue(self.Client.with_user(self.admin_user).search(client_domain))
        obligation_domain = [('id', '=', self.obligation_no_accountant.id)]
        self.assertFalse(
            self.Obligation.with_user(self.contador_a).search(obligation_domain)
        )
        self.assertTrue(
            self.Obligation.with_user(self.admin_user).search(obligation_domain)
        )

    def test_admin_sees_all_obligations(self):
        """RF-17: el administrador ve las obligaciones de todos los contadores."""
        visible = self.Obligation.with_user(self.admin_user).search([
            ('id', 'in', self._all_obligation_ids()),
        ])
        self.assertEqual(set(visible.ids), set(self._all_obligation_ids()))


@tagged('post_install', '-at_install')
class TestDueSoonTray(TransactionCase):
    """T8: bandeja "Próximos vencimientos" — vista, acción, filtros y menú (RF-18)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.partner = cls.env['res.partner'].create({'name': 'Partner T8 bandeja'})
        cls.client = cls.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente T8 bandeja',
            'partner_id': cls.partner.id,
            'company_id': cls.env.company.id,
        })

    def _create_manual_obligation(self, days_from_today):
        obligation = self.Obligation.create({
            'name': f'OBL-T8-{days_from_today}',
            'client_id': self.client.id,
        })
        obligation.due_date = fields.Date.today() + timedelta(days=days_from_today)
        return obligation

    def test_due_soon_list_view(self):
        """RF-18: la bandeja muestra cliente, tipo, período, quincena, vencimiento y estado."""
        view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_due_soon_list'
        )
        self.assertEqual(view.type, 'list')
        self.assertEqual(view.model, 'l10n.ve.obligation')
        for field_name in (
            'client_id', 'obligation_type_id', 'period', 'quincena', 'due_date', 'state',
        ):
            self.assertIn(f'name="{field_name}"', view.arch)
        self.assertIn('default_order="due_date asc"', view.arch)

    def test_due_soon_action(self):
        """RF-18: la acción abre las obligaciones pendientes con el filtro de 30 días."""
        action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon'
        )
        self.assertEqual(action.res_model, 'l10n.ve.obligation')
        self.assertEqual(action.view_mode, 'list,form')
        self.assertEqual(
            action.view_id,
            self.env.ref(
                'l10n_ve_compliance_manager.view_l10n_ve_obligation_due_soon_list'
            ),
        )
        self.assertEqual(
            safe_eval(action.domain),
            [('state', 'in', ('pending', 'overdue'))],
        )
        self.assertTrue(
            safe_eval(action.context).get('search_default_filter_due_30_days')
        )

    def test_due_soon_menu(self):
        """RF-18: el menú "Próximos vencimientos" cuelga de la raíz Cumplimiento VE."""
        menu = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_compliance_due_soon'
        )
        self.assertEqual(menu.name, 'Próximos vencimientos')
        self.assertEqual(
            menu.parent_id,
            self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_compliance_root'),
        )
        self.assertEqual(
            menu.action,
            self.env.ref(
                'l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon'
            ),
        )

    def test_due_soon_search_filters(self):
        """RF-18: existen los filtros Vencen esta semana, Vencidas, Mis clientes y 30 días."""
        view = self.env.ref('l10n_ve_compliance_manager.view_l10n_ve_obligation_search')
        for label in (
            'Vencen esta semana', 'Vencidas', 'Mis clientes', 'Próximos 30 días',
        ):
            self.assertIn(label, view.arch)

    def test_due_30_days_filter_limits_by_date(self):
        """RF-18: el filtro "Próximos 30 días" acota por fecha de vencimiento."""
        view = self.env.ref('l10n_ve_compliance_manager.view_l10n_ve_obligation_search')
        root = etree.fromstring(view.arch.encode())
        filter_elements = root.xpath("//filter[@name='filter_due_30_days']")
        self.assertEqual(
            len(filter_elements), 1, 'Debe existir el filtro "Próximos 30 días".',
        )
        domain = safe_eval(
            filter_elements[0].get('domain'),
            {'context_today': fields.Date.today, 'relativedelta': relativedelta},
        )
        inside = self._create_manual_obligation(10)
        outside = self._create_manual_obligation(60)
        found = self.Obligation.search(domain + [('id', 'in', (inside + outside).ids)])
        self.assertIn(inside, found)
        self.assertNotIn(outside, found)


@tagged('post_install', '-at_install')
class TestCopyCalendarWizard(TransactionCase):
    """T9: wizard "Copiar tabla a otro año" (RF-3, HU-4)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['l10n.ve.copy.calendar.wizard']
        cls.CalendarTable = cls.env['l10n.ve.seniat.calendar.table']

    def _source_table(self, code):
        return self.CalendarTable.search([('year', '=', 2026), ('code', '=', code)])

    def test_copy_2026_to_2027_duplicates_tables_and_lines(self):
        """RF-3/RF-14: copiar 2026 a 2027 duplica todas las tablas del año con sus líneas."""
        wizard = self.Wizard.create({'source_year': 2026, 'target_year': 2027})
        action = wizard.action_copy()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'l10n.ve.seniat.calendar.table')
        self.assertEqual(action['domain'], [('year', '=', 2027)])

        copied = self.CalendarTable.search([('year', '=', 2027)])
        self.assertEqual(
            set(copied.mapped('code')),
            {'a1', 'a2', 'est_islr', 'ret_islr'},
        )
        expected_lines = {'a1': 120, 'a2': 120, 'est_islr': 30, 'ret_islr': 120}
        for code, line_count in expected_lines.items():
            new_table = copied.filtered(lambda table: table.code == code)
            source = self._source_table(code)
            self.assertEqual(len(new_table.line_ids), line_count)
            self.assertEqual(new_table.month_offset, source.month_offset)
            self.assertEqual(
                {(line.month, line.rif_digit): line.day for line in new_table.line_ids},
                {(line.month, line.rif_digit): line.day for line in source.line_ids},
                f'Las líneas de {code} 2027 deben replicar mes/dígito/día de 2026.',
            )
            self.assertTrue(
                all(line.year == 2027 for line in new_table.line_ids),
                f'Las líneas de {code} 2027 deben apuntar al año destino.',
            )
        a1_copied = copied.filtered(lambda table: table.code == 'a1')
        spot = a1_copied.line_ids.filtered(
            lambda line: line.month == 1 and line.rif_digit == 0
        )
        self.assertEqual(spot.day, 28)
        a2_copied = copied.filtered(lambda table: table.code == 'a2')
        self.assertEqual(a2_copied.month_offset, '1')
        est_copied = copied.filtered(lambda table: table.code == 'est_islr')
        self.assertEqual(est_copied.month_offset, '0')
        ret_copied = copied.filtered(lambda table: table.code == 'ret_islr')
        self.assertEqual(ret_copied.month_offset, '1')

    def test_copy_rejects_existing_target_year(self):
        """RF-3: si el año destino ya tiene tablas el wizard lanza UserError."""
        self.CalendarTable.create({'year': 2027, 'code': 'a1'})
        wizard = self.Wizard.create({'source_year': 2026, 'target_year': 2027})
        with self.assertRaises(UserError):
            wizard.action_copy()
        self.assertEqual(len(self.CalendarTable.search([('year', '=', 2027)])), 1)

    def test_copy_rejects_missing_source_year(self):
        """Sin tablas en el año origen el wizard informa con UserError."""
        wizard = self.Wizard.create({
            'source_year': TEST_YEAR,
            'target_year': TEST_YEAR + 1,
        })
        with self.assertRaises(UserError):
            wizard.action_copy()

    def test_copy_wizard_view_and_action(self):
        """El wizard tiene vista form con los dos años y acción en diálogo."""
        view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_copy_calendar_wizard_form'
        )
        self.assertEqual(view.type, 'form')
        self.assertEqual(view.model, 'l10n.ve.copy.calendar.wizard')
        for field_name in ('source_year', 'target_year'):
            self.assertIn(f'name="{field_name}"', view.arch)
        action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_copy_calendar_wizard'
        )
        self.assertEqual(action.res_model, 'l10n.ve.copy.calendar.wizard')
        self.assertEqual(action.view_mode, 'form')
        self.assertEqual(action.target, 'new')

    def test_copy_button_in_calendar_list_view(self):
        """La lista del calendario ofrece el botón "Copiar a otro año" siempre visible."""
        view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_seniat_calendar_table_list'
        )
        self.assertIn('Copiar a otro año', view.arch)
        self.assertIn('display="always"', view.arch)


@tagged('post_install', '-at_install')
class TestCalendarIntegration(TransactionCase):
    """T10: flujo end-to-end del contador — cliente SPE → tipo quincenal → cron →
    quincenas generadas con vencimiento oficial → bandeja de próximos vencimientos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Obligation = cls.env['l10n.ve.obligation']
        cls.ObligationType = cls.env['l10n.ve.obligation.type']
        cls.Client = cls.env['l10n.ve.compliance.client']
        cls.BankHoliday = cls.env['l10n.ve.bank.holiday']
        cls.partner = cls.env['res.partner'].create({'name': 'Distribuidora T10'})
        cls.accountant = cls.env['res.users'].create({
            'name': 'Contador T10',
            'login': 'contador_t10',
            'email': 'contador.t10@example.com',
        })

    def _window_periods(self):
        today = fields.Date.today()
        next_month = today.month % 12 + 1
        next_year = today.year + (today.month == 12)
        return [(today.year, today.month), (next_year, next_month)]

    def _expected_due_date(self, code, year, month, rif_digit=5):
        """Recalcula el vencimiento con los datos oficiales crudos (día + offset
        de tabla + corrimiento a día hábil por fin de semana o feriado)."""
        table = self.env.ref(
            f'l10n_ve_compliance_manager.seniat_calendar_2026_{code}'
        )
        line = table.line_ids.filtered(
            lambda line: line.month == month and line.rif_digit == rif_digit
        )
        self.assertEqual(
            len(line), 1, f'Falta la línea {code} {month}/{year} dígito {rif_digit}.'
        )
        target_month = month + int(table.month_offset)
        target_year = year
        if target_month > 12:
            target_month, target_year = 1, year + 1
        due_date = date(target_year, target_month, line.day)
        while (
            due_date.weekday() >= 5
            or self.BankHoliday.search_count([('date', '=', due_date)])
        ):
            due_date += timedelta(days=1)
        return due_date

    def _client_obligations(self, client, obligation_type):
        return self.Obligation.search([
            ('client_id', '=', client.id),
            ('obligation_type_id', '=', obligation_type.id),
        ])

    def test_end_to_end_accountant_flow(self):
        """RF-6/RF-9–RF-13: el cron genera las 2 quincenas del cliente SPE con los
        vencimientos oficiales, sin duplicar, y la bandeja las muestra (RF-18)."""
        iva_quincenal = self.ObligationType.create({
            'name': 'IVA Quincenal Integración T10',
            'tax_type': 'iva',
            'periodicity': 'quincenal',
            'seniat_table_code': 'a1',
        })
        client = self.Client.create({
            'name': 'Sujeto Pasivo Especial T10',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-00000005-5',
            'is_spe': True,
            'accountant_id': self.accountant.id,
            'applicable_type_ids': [(6, 0, iva_quincenal.ids)],
        })

        self.Obligation._cron_generate_obligations()

        quincenas = self._client_obligations(client, iva_quincenal)
        self.assertEqual(
            len(quincenas), 4,
            'El cron debe crear 2 quincenas por cada mes de la ventana (mes actual + próximo).',
        )
        for year, month in self._window_periods():
            period = f'{month:02d}/{year}'
            q1 = quincenas.filtered(lambda o: o.period == period and o.quincena == 'q1')
            q2 = quincenas.filtered(lambda o: o.period == period and o.quincena == 'q2')
            self.assertEqual(len(q1), 1, f'{period} debe tener exactamente una obligación q1.')
            self.assertEqual(len(q2), 1, f'{period} debe tener exactamente una obligación q2.')
            self.assertEqual(q1.due_date, self._expected_due_date('a1', year, month))
            self.assertEqual(q2.due_date, self._expected_due_date('a2', year, month))
            self.assertGreaterEqual(
                q2.due_date,
                date(year + (month == 12), month % 12 + 1, 1),
                'RF-11: la 2da quincena vence en el mes siguiente al período.',
            )
            self.assertEqual(q1.state, 'pending')
            self.assertEqual(q2.state, 'pending')

        self.Obligation._cron_generate_obligations()
        self.assertEqual(
            len(self._client_obligations(client, iva_quincenal)), 4,
            'RF-13: correr el cron de nuevo no debe duplicar las quincenas.',
        )

        current_year, current_month = self._window_periods()[0]
        current_q1 = quincenas.filtered(
            lambda o: o.period == f'{current_month:02d}/{current_year}' and o.quincena == 'q1'
        )
        due_soon = self.Obligation.search([
            ('client_id', '=', client.id),
            ('state', 'in', ('pending', 'overdue')),
            ('due_date', '<=', fields.Date.today() + timedelta(days=30)),
        ])
        self.assertIn(
            current_q1, due_soon,
            'RF-18: la bandeja de próximos 30 días debe mostrar la quincena en curso.',
        )
        self.assertFalse(self.env['l10n.ve.alert'].search([
            ('client_id', '=', client.id),
            ('alert_type', '=', 'calendar_missing'),
        ]), 'RF-4: con el calendario 2026 cargado no debe haber alertas de calendario faltante.')
