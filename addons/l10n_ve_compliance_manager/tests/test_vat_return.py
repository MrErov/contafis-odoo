import base64
from io import BytesIO

import openpyxl
from odoo import fields
from odoo.tests import TransactionCase, tagged

from .common import TaxGroupMixin


@tagged('post_install', '-at_install')
class TestVatReturn(TaxGroupMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        # Aislar BD: limpiar datos de corridas previas
        self.env['l10n.ve.vat.book.line'].search([]).unlink()
        self.env['l10n.ve.vat.return'].search([]).unlink()
        self.env['l10n.ve.import.line'].search([]).unlink()
        self.env['l10n.ve.import.wizard'].search([]).unlink()

        self.company = self.env.company
        self.country = self.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not self.country:
            self.country = self.env['res.country'].create({'name': 'Venezuela', 'code': 'VE'})
        self.company.account_fiscal_country_id = self.country

        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test', 'vat': 'J-12345678-9'})
        self.customer = self.env['res.partner'].create({'name': 'Cliente Test', 'vat': 'V-98765432-1'})

        self.expense_account = self.env['account.account'].create({
            'name': 'Gastos Test', 'code': 'TSTEXP', 'account_type': 'expense',
        })
        self.income_account = self.env['account.account'].create({
            'name': 'Ingresos Test', 'code': 'TSTINC', 'account_type': 'income',
        })
        self.payable_account = self.env['account.account'].create({
            'name': 'CxP Test', 'code': 'TSTPAY', 'account_type': 'liability_payable',
        })
        self.receivable_account = self.env['account.account'].create({
            'name': 'CxC Test', 'code': 'TSTREC', 'account_type': 'asset_receivable',
        })

        self.journal_purchase = self.env['account.journal'].create({
            'name': 'Facturas Proveedor', 'type': 'purchase', 'code': 'TSTPUR',
            'default_account_id': self.expense_account.id,
        })
        self.journal_sale = self.env['account.journal'].create({
            'name': 'Facturas Cliente', 'type': 'sale', 'code': 'TSTSAL',
            'default_account_id': self.income_account.id,
        })

        self.partner.property_account_payable_id = self.payable_account
        self.customer.property_account_receivable_id = self.receivable_account

        self.tax_group = self._get_or_create_tax_group()

        self.tax_iva_16 = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16.0, 'type_tax_use': 'purchase',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })
        self.tax_iva_8 = self.env['account.tax'].create({
            'name': 'IVA 8%', 'amount': 8.0, 'type_tax_use': 'purchase',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })
        self.tax_iva_16_sale = self.env['account.tax'].create({
            'name': 'IVA 16% Venta', 'amount': 16.0, 'type_tax_use': 'sale',
            'amount_type': 'percent', 'tax_group_id': self.tax_group.id, 'country_id': self.country.id,
        })

    def _create_in_invoice(self, amount=1000.0, tax_ids=None, date='2026-08-15'):
        vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal_purchase.id,
            'invoice_date': fields.Date.to_date(date),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.expense_account.id,
                'tax_ids': [(6, 0, tax_ids or [])],
            })],
        }
        return self.env['account.move'].create(vals)

    def _create_out_invoice(self, amount=1000.0, tax_ids=None, date='2026-08-15'):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': fields.Date.to_date(date),
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto Test',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.income_account.id,
                'tax_ids': [(6, 0, tax_ids or [])],
            })],
        }
        return self.env['account.move'].create(vals)

    def _generate_book_lines(self, moves=None, period='2026-08'):
        """Helper: genera líneas de libro para los movimientos dados."""
        if moves is None:
            # Fallback: buscar facturas del período
            year, month = map(int, period.split('-'))
            date_from = fields.Date.to_date(f'{year}-{month:02d}-01')
            if month == 12:
                date_to = fields.Date.to_date(f'{year + 1}-01-01')
            else:
                date_to = fields.Date.to_date(f'{year}-{month + 1:02d}-01')

            domain = [
                ('company_id', '=', self.company.id),
                ('state', '!=', 'cancel'),
                ('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<', date_to),
            ]
            moves = self.env['account.move'].search(domain)

        for move in moves:
            self.env['l10n.ve.vat.book.line'].create_from_move(move)

    def test_vat_return_load_from_book(self):
        """Carga ítems desde vat.book.line."""
        # Crear facturas
        in_inv = self._create_in_invoice(1000.0, [self.tax_iva_16.id], '2026-08-10')
        in_inv.action_post()
        out_inv = self._create_out_invoice(2000.0, [self.tax_iva_16_sale.id], '2026-08-20')
        out_inv.action_post()

        self._generate_book_lines(moves=[in_inv, out_inv])

        # Crear planilla y cargar desde libro
        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return.action_load_from_book()

        # Verificar débitos (ventas)
        self.assertEqual(vat_return.item_42, 2000.0)  # base gravada 16%
        self.assertEqual(vat_return.item_43, 320.0)   # IVA 16% ventas

        # Verificar créditos (compras)
        self.assertEqual(vat_return.item_33, 1000.0)  # base gravada 16%
        self.assertEqual(vat_return.item_34, 160.0)   # IVA 16% compras

        # Verificar agregados
        self.assertEqual(vat_return.item_46, 2000.0)  # total bases ventas
        self.assertEqual(vat_return.item_47, 320.0)   # total IVA ventas = item_43
        self.assertEqual(vat_return.item_49, 320.0)   # total débitos
        self.assertEqual(vat_return.item_35, 1000.0)  # total bases compras
        self.assertEqual(vat_return.item_36, 160.0)   # total IVA compras

    def test_vat_return_excedente_arrastre(self):
        """item_60 positivo arrastra a item_20 del mes siguiente."""
        # IMPORTANTE: Crear planilla septiembre ANTES para que el arrastre en cascada funcione
        vat_return_sep = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-09',
            'company_id': self.company.id,
        })

        # Mes 1: créditos > débitos → excedente
        in_inv = self._create_in_invoice(2000.0, [self.tax_iva_16.id], '2026-08-10')
        in_inv.action_post()
        # Sin ventas → débitos = 0
        self._generate_book_lines(moves=[in_inv])

        vat_return_aug = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return_aug.action_load_from_book()

        # item_39 (créditos) = 320, item_49 (débitos) = 0
        # excedente = 320 - 0 = 320
        self.assertEqual(vat_return_aug.item_60, 320.0)
        self.assertEqual(vat_return_aug.item_53, 0.0)

        # item_20 de septiembre debe ser 320 (item_60 de agosto) por arrastre en cascada
        self.assertEqual(vat_return_sep.item_20, 320.0)

    def test_vat_return_pago_sin_excedente(self):
        """item_60 negativo → item_53 = pago, no hay arrastre."""
        # Mes 1: débitos > créditos → pago
        out_inv = self._create_out_invoice(2000.0, [self.tax_iva_16_sale.id], '2026-08-10')  # IVA 320 débito
        out_inv.action_post()
        # Sin compras → créditos = 0
        self._generate_book_lines(moves=[out_inv])

        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return.action_load_from_book()

        # item_39 = 0, item_49 = 320 → excedente = -320
        self.assertEqual(vat_return.item_60, 0.0)
        self.assertEqual(vat_return.item_53, 320.0)  # pago

    def test_vat_return_unique_constraint(self):
        """Constraint único por compañía y período - verifica que el constraint existe."""
        model = self.env['l10n.ve.vat.return']
        self.assertTrue(hasattr(model, '_unique_return'))
        unique_constraint = model._unique_return
        self.assertEqual(unique_constraint.name, 'unique_return')
        definition = unique_constraint.get_definition(model.pool)
        self.assertIn('company_id', definition)
        self.assertIn('period_month', definition)

    def test_vat_return_item_66_retenciones(self):
        """item_66 carga retenciones direction='by_buyer' (ventas)."""
        # Venta con retención (direction by_buyer)
        out_inv = self._create_out_invoice(2000.0, [self.tax_iva_16_sale.id], '2026-08-10')
        out_inv.action_post()

        # Crear retención en venta (simular que el cliente nos retiene)
        self.env['l10n.retention'].create({
            'partner_id': self.customer.id,
            'amount': 240.0,  # 75% de 320
            'currency_id': self.company.currency_id.id,
            'date': fields.Date.today(),
            'invoice_id': out_inv.id,
            'state': 'posted',
        })

        self._generate_book_lines(moves=[out_inv])

        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return.action_load_from_book()

        # item_66 debe tener la retención de la venta (by_buyer)
        self.assertEqual(vat_return.item_66, 240.0)

    def test_vat_return_action_calculate(self):
        """action_calculate recalcula agregados y autoliquidación."""
        in_inv = self._create_in_invoice(1000.0, [self.tax_iva_16.id], '2026-08-10')
        in_inv.action_post()
        out_inv = self._create_out_invoice(2000.0, [self.tax_iva_16_sale.id], '2026-08-20')
        out_inv.action_post()

        self._generate_book_lines(moves=[in_inv, out_inv])

        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return.action_load_from_book()

        # Modificar manualmente un item
        vat_return.item_48 = 50.0
        vat_return.action_calculate()

        # Debe recalcular item_49 = item_47 + item_48 - item_80
        self.assertEqual(vat_return.item_49, vat_return.item_47 + 50.0)

    def test_export_99030_generates_file(self):
        """Exporta la Planilla 99030 a Excel y verifica valores."""
        # Crear planilla con valores conocidos
        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
            'item_42': 1000.0,
            'item_43': 160.0,
            'item_33': 500.0,
            'item_34': 80.0,
            'item_53': 80.0,
            'item_60': 0.0,
            'item_90': 80.0,
        })
        result = vat_return.action_export_99030_xlsx()

        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('Planilla_99030_2026-08.xlsx', result['url'])
        self.assertTrue(vat_return.export_file)
        self.assertEqual(vat_return.export_filename, 'Planilla_99030_2026-08.xlsx')

        # Verificar contenido del XLSX
        xlsx = base64.b64decode(vat_return.export_file)
        wb = openpyxl.load_workbook(BytesIO(xlsx), data_only=True)
        ws = wb.active

        self.assertEqual(ws.title, 'PLANILLA 99030')

        # Verificar encabezado empresa
        self.assertEqual(ws.cell(row=1, column=1).value, 'FORMA IVA 99030')
        self.assertEqual(ws.cell(row=2, column=1).value, 'RIF:')
        self.assertEqual(ws.cell(row=3, column=1).value, 'Contribuyente:')
        self.assertEqual(ws.cell(row=4, column=1).value, 'Período:')

        # Verificar headers de tabla (fila 6)
        headers = [ws.cell(row=6, column=c).value for c in range(1, 4)]
        self.assertEqual(headers, ['Ítem', 'Concepto', 'Valor'])

        # Helper para buscar un ítem por código
        def find_item_row(item_code):
            for r in range(7, ws.max_row + 1):
                if ws.cell(row=r, column=1).value == item_code:
                    return r
            return None

        # Verificar item_42
        row_42 = find_item_row('42')
        self.assertIsNotNone(row_42, 'item_42 no encontrado')
        self.assertEqual(ws.cell(row=row_42, column=2).value, 'Ventas internas gravadas por alícuota general 16%')
        self.assertEqual(ws.cell(row=row_42, column=3).value, 1000.0)

        # Verificar item_43
        row_43 = find_item_row('43')
        self.assertIsNotNone(row_43, 'item_43 no encontrado')
        self.assertEqual(ws.cell(row=row_43, column=3).value, 160.0)

        # Verificar item_33 (en créditos)
        row_33 = find_item_row('33')
        self.assertIsNotNone(row_33, 'item_33 no encontrado')
        self.assertEqual(ws.cell(row=row_33, column=2).value, 'Compras internas gravadas solo por alícuota general 16%')
        self.assertEqual(ws.cell(row=row_33, column=3).value, 500.0)

        # Verificar item_90 (Total a Pagar)
        row_90 = find_item_row('90')
        self.assertIsNotNone(row_90, 'item_90 no encontrado')
        self.assertEqual(ws.cell(row=row_90, column=2).value, 'Total a Pagar')
        self.assertEqual(ws.cell(row=row_90, column=3).value, 80.0)

    def test_export_99030_headers_structure(self):
        """Verifica que el XLSX tiene las 3 secciones y 48 ítems."""
        vat_return = self.env['l10n.ve.vat.return'].create({
            'period_month': '2026-08',
            'company_id': self.company.id,
        })
        vat_return.action_export_99030_xlsx()

        xlsx = base64.b64decode(vat_return.export_file)
        wb = openpyxl.load_workbook(BytesIO(xlsx), data_only=True)
        ws = wb.active

        # Verificar 3 secciones existen
        sections_found = []
        items_found = set()

        for r in range(6, ws.max_row + 1):
            cell_val = ws.cell(row=r, column=1).value
            if cell_val in ('DÉBITOS FISCALES', 'CRÉDITOS FISCALES', 'AUTOLIQUIDACIÓN'):
                sections_found.append(cell_val)
            elif cell_val and str(cell_val).replace('.', '').isdigit():
                items_found.add(str(cell_val))

        self.assertEqual(sections_found, ['DÉBITOS FISCALES', 'CRÉDITOS FISCALES', 'AUTOLIQUIDACIÓN'])

        # Verificar que hay 59 ítems (comparar como sets, el orden no importa)
        item_codes_expected = {
            '40', '41', '42', '43', '442', '443', '452', '453', '46', '47', '48', '80', '49',
            '30', '31', '32', '312', '313', '322', '323', '33', '34', '332', '333', '342', '343',
            '35', '36', '70', '37', '71', '20', '21', '81', '38', '82', '39',
            '53', '60', '22', '51', '24', '78', '54', '66', '72', '73', '74',
            '55', '67', '56', '57', '68', '75', '76', '77', '58', '69', '90'
        }
        self.assertEqual(items_found, item_codes_expected)
        self.assertEqual(len(items_found), 59)

    def test_pdf_vat_return_conceptos_corregidos(self):
        """Verifica que el PDF QWeb usa conceptos SENIAT literales."""
        template = self.env.ref(
            'l10n_ve_compliance_manager.report_vat_return_99030'
        )
        arch = template.arch or ''

        # Conceptos clave corregidos (SENIAT exactos)
        self.assertIn('TOTAL IMPUESTO DEL PERÍODO', arch)
        self.assertIn('Total a Pagar', arch)
        self.assertIn('Créditos adquiridos por cesión de retenciones', arch)
        self.assertIn('Créditos fiscales totalmente deducibles', arch)
        self.assertIn('Impuesto pagado en declaración(es) sustituida(s)', arch)

        # Verificar que conceptos viejos NO están
        self.assertNotIn('IVA a pagar', arch)
        self.assertNotIn('Observaciones', arch)
        self.assertNotIn('Total a pagar', arch)  # old concept for item_72
        self.assertNotIn('Otros créditos', arch)  # old concept for item_70
        self.assertNotIn('Excedente a favor', arch)  # old concept for item_22
        self.assertNotIn('Excedente arrastre', arch)  # old concept for item_20
