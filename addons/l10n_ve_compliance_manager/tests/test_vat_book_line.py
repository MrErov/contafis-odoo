from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install')
class TestVatBookLine(TransactionCase):

    def setUp(self):
        super().setUp()
        # Limpiar líneas de libro de IVA preexistentes para evitar conflictos de constraint único
        self.env['l10n.ve.vat.book.line'].search([]).unlink()
        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test'})
        self.company = self.env.company

    def test_vat_book_line_create_purchase(self):
        """Crear línea de libro para compra."""
        line = self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-001',
            'control_number': 'CTRL-001',
            'operation_code': '33',
            'base_general': 1000.0,
            'vat_general': 160.0,
            'company_id': self.company.id,
        })
        self.assertEqual(line.book_type, 'purchase')
        self.assertEqual(line.base_general, 1000.0)
        self.assertEqual(line.vat_general, 160.0)

    def test_vat_book_line_create_sale(self):
        """Crear línea de libro para venta."""
        line = self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'sale',
            'period_month': '2026-08',
            'partner_id': self.partner.id,
            'invoice_number': 'FAC-002',
            'control_number': 'CTRL-002',
            'operation_code': '42',
            'base_general': 2000.0,
            'vat_general': 320.0,
            'company_id': self.company.id,
        })
        self.assertEqual(line.book_type, 'sale')
        self.assertEqual(line.operation_code, '42')

    def test_vat_book_line_unique_constraint(self):
        """Constraint único evita duplicados - verifica que el constraint existe en el modelo."""
        model = self.env['l10n.ve.vat.book.line']
        # Verificar que existe el atributo _unique_line (models.Constraint)
        self.assertTrue(hasattr(model, '_unique_line'))
        unique_constraint = model._unique_line
        # Verificar que el constraint tiene el nombre correcto
        self.assertEqual(unique_constraint.name, 'unique_line')

    def test_vat_book_unique_constraint_extended(self):
        """Constraint permite misma factura con distinto operation_code o retention_direction."""
        partner = self.env['res.partner'].create({'name': 'Test', 'vat': 'J-12345678-9'})

        # Base: operation_code='33', direction='to_vendor'
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase', 'period_month': '2026-08',
            'partner_id': partner.id, 'invoice_number': '001',
            'control_number': '001', 'operation_code': '33',
            'retention_direction': 'to_vendor', 'company_id': self.env.company.id,
        })

        # Distinto operation_code → OK
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase', 'period_month': '2026-08',
            'partner_id': partner.id, 'invoice_number': '001',
            'control_number': '001', 'operation_code': '333',
            'retention_direction': 'to_vendor', 'company_id': self.env.company.id,
        })

        # Distinta retention_direction → OK
        self.env['l10n.ve.vat.book.line'].create({
            'book_type': 'purchase', 'period_month': '2026-08',
            'partner_id': partner.id, 'invoice_number': '001',
            'control_number': '001', 'operation_code': '33',
            'retention_direction': 'to_third', 'company_id': self.env.company.id,
        })

        # Duplicado exacto → DEBE fallar con IntegrityError
        with self.assertRaises(IntegrityError):
            self.env['l10n.ve.vat.book.line'].create({
                'book_type': 'purchase', 'period_month': '2026-08',
                'partner_id': partner.id, 'invoice_number': '001',
                'control_number': '001', 'operation_code': '33',
                'retention_direction': 'to_vendor', 'company_id': self.env.company.id,
            })

    def test_get_operation_code_for_rate(self):
        """Verifica mapeo de tasas a códigos SENIAT."""
        # Ventas
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(16, 'sale'),
            '42'
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(8, 'sale'),
            '443'
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(18, 'sale'),
            '442'
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(0, 'sale'),
            '40'
        )
        # Compras
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(16, 'purchase'),
            '33'
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(8, 'purchase'),
            '333'  # Base reducida (item_333), no 343 que es el IVA
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(18, 'purchase'),
            '332'
        )
        self.assertEqual(
            self.env['l10n.ve.vat.book.line']._get_operation_code_for_rate(0, 'purchase'),
            '30'
        )
