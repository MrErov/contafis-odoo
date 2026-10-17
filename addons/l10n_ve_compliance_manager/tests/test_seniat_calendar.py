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
