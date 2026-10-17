from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install')
class TestSeniatCalendarModels(TransactionCase):
    """T1: modelos del calendario SENIAT (tabla por año + líneas mes/dígito)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CalendarTable = cls.env['l10n.ve.seniat.calendar.table']
        cls.CalendarLine = cls.env['l10n.ve.seniat.calendar']

    def _create_table(self, **kwargs):
        vals = {'year': 2026, 'code': 'a1'}
        vals.update(kwargs)
        return self.CalendarTable.create(vals)

    def test_create_table_with_lines(self):
        """Crear tabla con líneas: name computado y líneas enlazadas."""
        table = self._create_table(line_ids=[
            (0, 0, {'month': 1, 'rif_digit': 0, 'day': 28}),
        ])
        self.assertEqual(table.name, '2026 — a.1 (1ra quincena)')
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
        self.assertEqual(line.year, 2026)
        found = self.CalendarLine.search([
            ('year', '=', 2026), ('month', '=', 2), ('rif_digit', '=', 5),
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
        table_2027 = self._create_table(year=2027)
        self.assertTrue(table_2027.id)

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
