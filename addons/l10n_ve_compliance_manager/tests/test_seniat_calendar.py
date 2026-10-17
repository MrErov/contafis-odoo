from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import convert
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
