import base64
from io import BytesIO
from pathlib import Path

import openpyxl
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImportCartelera(TransactionCase):
    """Tests para importación de cartelera fiscal (Fase C)."""

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['l10n.ve.import.wizard']
        self.Client = self.env['l10n.ve.compliance.client']
        self.Partner = self.env['res.partner']
        self.Status = self.env['l10n.ve.cartelera.status']
        self.DocType = self.env['l10n.ve.document.type']

    def _create_cartelera_excel(self, rows_data, sheet_name='enero'):
        """
        Genera un Excel en memoria con estructura de cartelera fiscal.

        Args:
            rows_data: Lista de dicts con claves:
                - rif: RIF de la empresa
                - name: Nombre de la empresa
                - statuses: dict {C01: True, C02: False, ...} (36 códigos)
            sheet_name: Nombre de la hoja (default 'enero')

        Returns:
            bytes: Contenido del archivo xlsx
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        # Filas 1-2: encabezados de sección fusionados (IGNORAR)
        ws.merge_cells('A1:AN1')
        ws['A1'] = 'CARTELERA FISCAL - SENIAT, IVSS, INCES, BANAVIH, MINTRA, ALCALDÍA'
        ws.merge_cells('A2:AN2')
        ws['A2'] = 'Período: Enero 2026'

        # Obtener tipos de documento en orden de código C01..C36
        doc_types = self.DocType.search([
            ('required_for', '=', 'company')
        ], order='code')
        codes = [dt.code for dt in doc_types]
        names = [dt.name for dt in doc_types]

        # Fila 3: headers con NOMBRES de documentos (no códigos)
        # Enero: RIF en C(3), Nombre en D(4), Docs en E..AN(5..40)
        ws.cell(row=3, column=1, value='Item')
        ws.cell(row=3, column=2, value='Otro')
        ws.cell(row=3, column=3, value='RIF')
        ws.cell(row=3, column=4, value='Empresa')
        for i, name in enumerate(names):
            ws.cell(row=3, column=5 + i, value=name)

        # Columnas AO, AP: Total y % (IGNORAR)
        ws.cell(row=3, column=41, value='Total')
        ws.cell(row=3, column=42, value='%')

        # Filas 4+: datos de empresas
        for row_idx, row_data in enumerate(rows_data, 4):
            ws.cell(row=row_idx, column=3, value=row_data['rif'])  # Col C
            ws.cell(row=row_idx, column=4, value=row_data['name'])  # Col D
            ws.cell(row=row_idx, column=2, value=row_idx - 3)  # Col B: Item
            ws.cell(row=row_idx, column=1, value='')  # Col A

            statuses = row_data.get('statuses', {})
            for i, code in enumerate(codes):
                ws.cell(row=row_idx, column=5 + i, value=statuses.get(code, False))

            # Columnas AO, AP vacías
            ws.cell(row=row_idx, column=41, value='')
            ws.cell(row=row_idx, column=42, value='')

        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    def _create_nonjanuary_cartelera_excel(self, rows_data, sheet_name='febrero'):
        """
        Genera un Excel con la estructura real de feb/dic.

        Diferencias con enero (archivo real verificado):
        - No hay celda "RIF" en la fila de encabezados (fuerza el sniffing).
        - La fila-ejemplo trae un RIF ficticio en A/B ("J000000001") y los
          datos reales viven en C (RIF) y D (nombre).
        - Los labels de documentos empiezan en la columna C, dos columnas
          a la izquierda de los datos (E..AN).
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        ws.merge_cells('A1:AN1')
        ws['A1'] = 'CARTELERA FISCAL - SENIAT, IVSS, INCES, BANAVIH, MINTRA, ALCALDÍA'
        ws['A2'] = 'RIF'
        ws['B2'] = 'Empresas/ Firmas Personales'

        doc_types = self.DocType.search([
            ('required_for', '=', 'company')
        ], order='code')
        codes = [dt.code for dt in doc_types]
        names = [dt.name for dt in doc_types]

        # Labels desplazados: C01 en C(3), C02 en D(4), ... datos en E(5)+
        for i, name in enumerate(names):
            ws.cell(row=3, column=3 + i, value=name)
        ws.cell(row=3, column=41, value='Total')
        ws.cell(row=3, column=42, value='Porcentaje')

        # Fila-ejemplo del archivo real (A/B), ignorada por el parser
        ws.cell(row=4, column=1, value='J000000001')
        ws.cell(row=4, column=2, value='Empresa, c.a.')

        for row_idx, row_data in enumerate(rows_data, 4):
            ws.cell(row=row_idx, column=3, value=row_data['rif'])  # Col C
            ws.cell(row=row_idx, column=4, value=row_data['name'])  # Col D

            statuses = row_data.get('statuses', {})
            for i, code in enumerate(codes):
                ws.cell(row=row_idx, column=5 + i, value=statuses.get(code, False))

        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    def _create_wizard(self, import_type='cartelera', year=2026, month='1'):
        """Helper para crear wizard con datos por defecto."""
        return self.Wizard.create({
            'import_type': import_type,
            'cartelera_year': year,
            'cartelera_month': month,
        })

    def _fixture_path(self, filename):
        return Path(__file__).parent / 'fixtures' / filename

    def _compute_expected_rows_from_fixture(self, sheet_name='enero'):
        """Computa los esperados del parser leyendo el fixture real.

        Geometría de Control_Cartelera_Fiscal_Prueba.xlsx (verificada):
        - Datos desde la fila 4; RIF en C, nombre en D.
        - 36 estatus C01..C36 posicionales en E..AN (columnas 5..40).
        - La fila de encabezados (3) está desplazada una columna a la
          izquierda de los datos (ej. "Total" cae sobre la columna de C36).
        """
        wb = openpyxl.load_workbook(
            self._fixture_path('Control_Cartelera_Fiscal_Prueba.xlsx'),
            data_only=True,
        )
        ws = wb[sheet_name]
        expected_rows = []
        row_idx = 4
        while True:
            rif = ws.cell(row=row_idx, column=3).value
            name = ws.cell(row=row_idx, column=4).value
            if not rif and not name:
                break
            statuses = {}
            for i in range(36):
                code = f'C{i + 1:02d}'
                value = ws.cell(row=row_idx, column=5 + i).value
                if isinstance(value, bool):
                    statuses[code] = value
                elif value is None:
                    statuses[code] = False
                else:
                    statuses[code] = str(value).strip().lower() in (
                        '1', 'true', 'verdadero', 'si', 'sí', 'yes', 'x')
            expected_rows.append({
                'rif': str(rif).strip().upper(),
                'name': str(name).strip(),
                'statuses': statuses,
            })
            row_idx += 1
        return expected_rows

    def test_parse_cartelera_sheet(self):
        """Generar wizard, cargar Excel, verificar que se crean 2 import.line."""
        # Preparar datos: 2 empresas
        rows_data = [
            {
                'rif': 'J-31527189-4',
                'name': 'Empresa Test 1',
                'statuses': {f'C{i:02d}': (i <= 2) for i in range(1, 37)},  # C01=True, C02=True, resto False
            },
            {
                'rif': 'V-12345678-5',
                'name': 'Empresa Test 2',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},  # todos True
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
        })

        # Cargar archivo (para cartelera salta directo a preview)
        wizard.action_load_file()

        # Verificar que se crearon 2 líneas
        self.assertEqual(len(wizard.line_ids), 2)

        # Verificar datos de la primera línea
        line1 = wizard.line_ids.sorted('row_index')[0]
        self.assertEqual(line1.data['rif'], 'J-31527189-4')
        self.assertEqual(line1.data['name'], 'Empresa Test 1')
        self.assertEqual(line1.data['year'], 2026)
        self.assertEqual(line1.data['month'], '1')
        self.assertTrue(line1.data['statuses']['C01'])
        self.assertTrue(line1.data['statuses']['C02'])
        self.assertFalse(line1.data['statuses']['C03'])
        self.assertEqual(len(line1.data['statuses']), 36)

        # Verificar datos de la segunda línea
        line2 = wizard.line_ids.sorted('row_index')[1]
        self.assertEqual(line2.data['rif'], 'V-12345678-5')
        self.assertEqual(line2.data['name'], 'Empresa Test 2')
        self.assertTrue(all(line2.data['statuses'].values()))

    def test_parse_nonjanuary_structure_sniffs_rif_column(self):
        """feb/dic: el sniffing elige la columna C y descarta el dummy A/B.

        Simula la hoja real (sin celda "RIF" en los headers, fila-ejemplo
        con "J000000001" en A/B y datos reales en C/D/E..): antes se
        generaba una línea basura con el RIF de ejemplo y el parseo se
        cortaba en la segunda fila.
        """
        rows_data = [
            {
                'rif': 'J-44444444-4',
                'name': 'Empresa Febrero 1',
                'statuses': {f'C{i:02d}': (i <= 3) for i in range(1, 37)},
            },
            {
                'rif': 'V-12345678-5',
                'name': 'Empresa Febrero 2',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        for sheet_name, month in (('febrero', '2'), ('diciembre', '12')):
            with self.subTest(sheet=sheet_name):
                excel_content = self._create_nonjanuary_cartelera_excel(
                    rows_data, sheet_name)

                wizard = self._create_wizard(year=2026, month=month)
                wizard.write({
                    'file': base64.b64encode(excel_content),
                    'filename': f'cartelera_{sheet_name}.xlsx',
                })
                wizard.action_load_file()

                self.assertEqual(len(wizard.line_ids), 2)
                self.assertFalse(wizard.cartelera_unmatched_headers)

                lines = wizard.line_ids.sorted('row_index')
                self.assertEqual(lines[0].data['rif'], 'J-44444444-4')
                self.assertEqual(lines[0].data['name'], 'Empresa Febrero 1')
                self.assertEqual(lines[1].data['rif'], 'V-12345678-5')
                self.assertEqual(lines[1].data['name'], 'Empresa Febrero 2')
                for line in lines:
                    self.assertNotEqual(line.data['rif'], 'J000000001')
                    self.assertEqual(len(line.data['statuses']), 36)
                self.assertTrue(lines[0].data['statuses']['C03'])
                self.assertFalse(lines[0].data['statuses']['C04'])

    def _assert_real_cartelera_fixture(self, sheet_name, month):
        """Parsea el fixture real en una hoja y compara con los esperados."""
        expected_rows = self._compute_expected_rows_from_fixture(sheet_name)
        self.assertEqual(len(expected_rows), 10)

        wizard = self._create_wizard(year=2026, month=month)
        wizard.write({
            'file': base64.b64encode(
                self._fixture_path('Control_Cartelera_Fiscal_Prueba.xlsx').read_bytes()
            ),
            'filename': 'Control_Cartelera_Fiscal_Prueba.xlsx',
        })
        wizard.action_load_file()

        self.assertEqual(len(wizard.line_ids), len(expected_rows))
        self.assertFalse(wizard.cartelera_unmatched_headers)

        lines = wizard.line_ids.sorted('row_index')
        for line, expected in zip(lines, expected_rows):
            self.assertEqual(line.data['rif'], expected['rif'])
            self.assertEqual(line.data['name'], expected['name'])
            self.assertEqual(len(line.data['statuses']), 36)
            self.assertEqual(line.data['statuses'], expected['statuses'])

    def test_parse_real_cartelera_fixture_enero(self):
        """Parser contra el fixture real de cartelera (hoja enero).

        Verifica estructura detectada, 10 empresas y los 36 estatus
        exactos de cada una, incluido C36 (regresión: en el archivo real
        el label "Total" cae sobre la columna de C36).
        """
        self._assert_real_cartelera_fixture('enero', '1')

    def test_parse_real_cartelera_fixture_febrero(self):
        """Parser contra el fixture real (hoja febrero).

        Regresión del sniffing: la hoja real trae la fila-ejemplo con RIF
        ficticio en A/B y los datos reales en C/D; sin sniffing se generaba
        una línea basura ("J000000001") y el parseo se cortaba en la fila 5.
        """
        self._assert_real_cartelera_fixture('febrero', '2')

    def test_import_cartelera_creates_client(self):
        """La primera empresa no existe → se crea res.partner + compliance.client."""
        rows_data = [
            {
                'rif': 'J-44444444-4',
                'name': 'Empresa Nueva',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'lax',
        })

        wizard.action_load_file()
        # Validar sintaxis
        for line in wizard.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()

        # Importar
        wizard.action_import()

        # Verificar que se creó partner
        partner = self.Partner.search([('vat', '=', 'J-44444444-4')])
        self.assertTrue(partner.exists())
        self.assertEqual(partner.name, 'Empresa Nueva')

        # Verificar que se creó cliente compliance
        client = self.Client.search([('rif', '=', 'J-44444444-4')])
        self.assertTrue(client.exists())
        self.assertEqual(client.name, 'Empresa Nueva')
        self.assertEqual(client.partner_id, partner)

    def test_import_cartelera_creates_snapshots(self):
        """2 clientes × 1 mes × 36 docs = 72 cartelera.status."""
        rows_data = [
            {
                'rif': 'J-55555555-5',
                'name': 'Empresa Snapshot 1',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
            {
                'rif': 'J-66666666-6',
                'name': 'Empresa Snapshot 2',
                'statuses': {f'C{i:02d}': (i % 2 == 0) for i in range(1, 37)},
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'lax',
        })

        wizard.action_load_file()
        for line in wizard.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()

        wizard.action_import()

        # Verificar snapshots creados
        snapshots = self.Status.search([
            ('year', '=', 2026),
            ('month', '=', '1'),
        ])

        # 2 clientes * 36 tipos = 72 snapshots
        self.assertEqual(len(snapshots), 72)

        # Verificar cliente 1: todos valid
        client1 = self.Client.search([('rif', '=', 'J-55555555-5')])
        snapshots1 = snapshots.filtered(lambda s: s.client_id == client1)
        self.assertEqual(len(snapshots1), 36)
        self.assertTrue(all(s.state == 'valid' for s in snapshots1))

        # Verificar cliente 2: alternados
        client2 = self.Client.search([('rif', '=', 'J-66666666-6')])
        snapshots2 = snapshots.filtered(lambda s: s.client_id == client2)
        self.assertEqual(len(snapshots2), 36)
        for snap in snapshots2:
            code_num = int(snap.document_type_id.code[1:])
            expected = (code_num % 2 == 0)
            self.assertEqual(snap.state == 'valid', expected,
                             f"{snap.document_type_id.code}: expected {expected}, got {snap.state}")

    def test_import_cartelera_upsert(self):
        """Importar el mismo mes 2 veces → no duplica snapshots."""
        rows_data = [
            {
                'rif': 'J-77777777-7',
                'name': 'Empresa Upsert',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        # Primera importación
        wizard1 = self._create_wizard(year=2026, month='1')
        wizard1.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'lax',
        })
        wizard1.action_load_file()
        for line in wizard1.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()
        wizard1.action_import()

        snapshots_after_first = self.Status.search_count([
            ('year', '=', 2026),
            ('month', '=', '1'),
        ])
        self.assertEqual(snapshots_after_first, 36)

        # Segunda importación (mismo archivo)
        wizard2 = self._create_wizard(year=2026, month='1')
        wizard2.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'lax',
        })
        wizard2.action_load_file()
        for line in wizard2.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()
        wizard2.action_import()

        # Verificar que no se duplicaron
        snapshots_after_second = self.Status.search_count([
            ('year', '=', 2026),
            ('month', '=', '1'),
        ])
        self.assertEqual(snapshots_after_second, 36,
                         'Segunda importación no debe duplicar snapshots')

    def test_parse_cartelera_invalid_sheet(self):
        """Hoja inexistente → UserError claro."""
        rows_data = [
            {
                'rif': 'J-88888888-8',
                'name': 'Empresa Test',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        # Crear Excel con hoja 'invalid' en lugar de 'enero'
        excel_content = self._create_cartelera_excel(rows_data, 'invalid')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
        })

        with self.assertRaises(UserError) as cm:
            wizard.action_load_file()

        self.assertIn("no existe en el archivo", str(cm.exception))

    def test_validate_business_cartelera(self):
        """Validación nivel 3 para cartelera."""
        wizard = self._create_wizard(year=2026, month='1')

        # Test 1: RIF vacío
        line = self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': 1,
            'data': {
                'rif': '',
                'name': 'Test',
                'year': 2026,
                'month': '1',
                'statuses': {f'C{i:02d}': False for i in range(1, 37)},
            },
            'state': 'draft',
        })
        line._validate_business()
        self.assertEqual(line.state, 'error')
        self.assertIn('rif no puede estar vacío', line.error_msg)

        # Test 2: Year fuera de rango
        line2 = self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': 2,
            'data': {
                'rif': 'J-31527189-4',
                'name': 'Test',
                'year': 2019,  # < 2020
                'month': '1',
                'statuses': {f'C{i:02d}': False for i in range(1, 37)},
            },
            'state': 'draft',
        })
        line2._validate_business()
        self.assertEqual(line2.state, 'error')
        self.assertIn('year debe estar entre 2020 y 2100', line2.error_msg)

        # Test 3: Month inválido
        line3 = self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': 3,
            'data': {
                'rif': 'J-31527189-4',
                'name': 'Test',
                'year': 2026,
                'month': '13',  # > 12
                'statuses': {f'C{i:02d}': False for i in range(1, 37)},
            },
            'state': 'draft',
        })
        line3._validate_business()
        self.assertEqual(line3.state, 'error')
        self.assertIn('month debe estar entre 1 y 12', line3.error_msg)

        # Test 4: Statuses faltando claves
        line4 = self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': 4,
            'data': {
                'rif': 'J-31527189-4',
                'name': 'Test',
                'year': 2026,
                'month': '1',
                'statuses': {'C01': True},  # Solo 1 clave
            },
            'state': 'draft',
        })
        line4._validate_business()
        self.assertEqual(line4.state, 'error')
        self.assertIn("statuses debe incluir clave 'C02'", line4.error_msg)

        # Test 5: Statuses con clave extra
        line5 = self.env['l10n.ve.import.line'].create({
            'wizard_id': wizard.id,
            'row_index': 5,
            'data': {
                'rif': 'J-31527189-4',
                'name': 'Test',
                'year': 2026,
                'month': '1',
                'statuses': {**{f'C{i:02d}': False for i in range(1, 37)}, 'C99': True},
            },
            'state': 'draft',
        })
        line5._validate_business()
        self.assertEqual(line5.state, 'error')
        self.assertIn("statuses contiene clave inválida 'C99'", line5.error_msg)

    def test_import_cartelera_strict_mode_no_client(self):
        """Modo strict: cliente no existe → error."""
        rows_data = [
            {
                'rif': 'J-99999999-9',
                'name': 'Empresa Strict',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'strict',
        })

        wizard.action_load_file()
        for line in wizard.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()

        with self.assertRaises(UserError) as cm:
            wizard.action_import()

        # En modo strict, action_import lanza error genérico al detectar línea con error
        self.assertIn("abortada en modo estricto", str(cm.exception))
        # El error original está en line.error_msg (pero la transacción hace rollback al lanzar excepción)

    def test_import_cartelera_via_action_import(self):
        """Verifica que action_import() enruta a _import_cartelera_line()."""
        rows_data = [
            {
                'rif': 'J-11111111-1',
                'name': 'Empresa Action Import',
                'statuses': {f'C{i:02d}': True for i in range(1, 37)},
            },
        ]

        excel_content = self._create_cartelera_excel(rows_data, 'enero')
        excel_b64 = base64.b64encode(excel_content)

        wizard = self._create_wizard(year=2026, month='1')
        wizard.write({
            'file': excel_b64,
            'filename': 'cartelera_test.xlsx',
            'mode': 'lax',
        })

        # Cargar archivo (llama _load_cartelera_file internamente)
        wizard.action_load_file()

        # Validar líneas
        for line in wizard.line_ids:
            line._validate_syntax()
            line._validate_reference()
            line._validate_business()

        # Ejecutar action_import (debe enrutar a _import_cartelera_line)
        wizard.action_import()

        # Verificar que se creó 1 cartelera.status
        snapshots = self.Status.search([
            ('year', '=', 2026),
            ('month', '=', '1'),
        ])
        self.assertEqual(len(snapshots), 36, 'Debe crear 36 snapshots (1 cliente x 36 tipos)')

        # Verificar que NO hay líneas con error
        error_lines = wizard.line_ids.filtered(lambda line: line.state == 'error')
        self.assertEqual(len(error_lines), 0, 'No debe haber líneas con error')

        # Verificar que la línea quedó en state='imported'
        imported_lines = wizard.line_ids.filtered(lambda line: line.state == 'imported')
        self.assertEqual(len(imported_lines), 1, 'Debe haber 1 línea importada')

        # Verificar que se creó el cliente
        client = self.Client.search([('rif', '=', 'J-11111111-1')])
        self.assertTrue(client.exists())
        self.assertEqual(client.name, 'Empresa Action Import')
