import base64
import json
from unittest.mock import patch

import odoo.addons.l10n_ve_compliance_manager.models.digitize_client as digitize_client_module
import requests
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_digitize_wizard import (
    DIGITIZE_URL,
    VALID_RESPONSE,
    DigitizeTestMixin,
    _load_fixture,
    _make_response,
)


def _jpeg_b64(byte):
    """Imagen JPEG realista en base64 (magic bytes ffd8ff)."""
    return base64.b64encode(b'\xff\xd8\xff\xe0' + byte * 40).decode()


@tagged('post_install', '-at_install')
class TestDigitizeBatch(DigitizeTestMixin, TransactionCase):
    """Batch de hasta 20 recibos en el wizard de digitalización (plan 007-B)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _batch_wizard(self, rows=2, **vals):
        """Wizard con N líneas de lote (cero red real fuera del Post).

        ``rows`` puede ser un entero (N filas por defecto) o una lista de
        dicts con overrides por fila (``image``, ``filename``, ...). La fila
        i lleva por defecto ``filename='recibo-0i.jpg'`` e imagen propia.
        """
        if isinstance(rows, int):
            specs = [{} for _ in range(rows)]
        else:
            specs = rows
        image = _jpeg_b64(b'a')
        commands = []
        for index, spec in enumerate(specs):
            row = {
                'filename': f'recibo-{index + 1:02d}.jpg',
                'image': image,
            }
            row.update(spec)
            commands.append((0, 0, row))
        defaults = {
            'type': 'purchase',
            'document_type_hint': 'auto',
            'line_ids': commands,
        }
        defaults.update(vals)
        return self.env['l10n.ve.digitize.wizard'].create(defaults)

    def _lines(self, wizard):
        return wizard.line_ids.sorted('id')

    def _run_batch(self, wizard, **patch_kwargs):
        """Ejecuta el lote con ``requests.post`` mockeado y sesión simulada."""
        with patch('requests.post', **patch_kwargs) as mock_post, \
                self._patch_session('sid-batch'):
            wizard.action_digitize_batch()
        return mock_post

    def _analyzed_batch(self, rows=1, payload=None):
        """Lote ya analizado con la respuesta realista del fixture (cero red)."""
        wizard = self._batch_wizard(rows=rows)
        self._run_batch(
            wizard, return_value=_make_response(200, payload or _load_fixture())
        )
        return wizard

    # ------------------------------------------------------------------
    # 1-15
    # ------------------------------------------------------------------
    def test_batch_processes_three_lines(self):
        """3 líneas válidas -> 3 POST, las 3 analizadas, sin tocar el estado single."""
        wizard = self._batch_wizard(rows=3)

        mock_post = self._run_batch(
            wizard, return_value=_make_response(200, VALID_RESPONSE)
        )

        self.assertEqual(mock_post.call_count, 3)
        for line in self._lines(wizard):
            self.assertEqual(line.status, 'done')
            self.assertFalse(line.error_message)
            result = json.loads(line.result_json)
            self.assertEqual(result['document_type'], 'factura_z')
            self.assertEqual(result['confidence'], 0.87)
        self.assertEqual(wizard.state, 'draft')

    def test_batch_rejects_more_than_twenty_lines(self):
        """21 líneas abortan el lote con ValidationError antes de cualquier POST."""
        wizard = self._batch_wizard(rows=21)

        with patch('requests.post') as mock_post, self._patch_session('sid-batch'):
            with self.assertRaises(ValidationError):
                wizard.action_digitize_batch()

        mock_post.assert_not_called()
        for line in self._lines(wizard):
            self.assertEqual(line.status, 'pending')

    def test_batch_rejects_empty_batch(self):
        """Un lote sin líneas aborta con ValidationError y sin POST."""
        wizard = self._batch_wizard(rows=0)

        with patch('requests.post') as mock_post, self._patch_session('sid-batch'):
            with self.assertRaises(ValidationError):
                wizard.action_digitize_batch()

        mock_post.assert_not_called()

    def test_batch_isolates_line_timeout(self):
        """El timeout de una línea queda en la línea; la siguiente se procesa igual."""
        wizard = self._batch_wizard(rows=2)

        mock_post = self._run_batch(
            wizard,
            side_effect=[requests.Timeout('t'), _make_response(200, VALID_RESPONSE)],
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('tardó demasiado', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 2)

    def test_batch_isolates_line_invalid_json(self):
        """Un 200 con cuerpo no-JSON marca la línea error y sigue la corrida."""
        wizard = self._batch_wizard(rows=2)

        mock_post = self._run_batch(
            wizard,
            side_effect=[_make_response(200, None), _make_response(200, VALID_RESPONSE)],
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('no es JSON', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 2)

    def test_batch_isolates_line_http_503(self):
        """503 en la línea 1 no aborta la línea 2."""
        wizard = self._batch_wizard(rows=2)

        mock_post = self._run_batch(
            wizard,
            side_effect=[_make_response(503), _make_response(200, VALID_RESPONSE)],
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('no está disponible', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 2)

    def test_batch_isolates_line_http_401(self):
        """401 en la línea 1 marca error de sesión y no aborta el lote."""
        wizard = self._batch_wizard(rows=2)

        mock_post = self._run_batch(
            wizard,
            side_effect=[_make_response(401), _make_response(200, VALID_RESPONSE)],
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('sesión de Odoo expiró', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 2)

    def test_batch_line_without_image_sets_error(self):
        """Recibo sin imagen -> error por ítem, el resto del lote sigue."""
        wizard = self._batch_wizard(rows=[{'image': False}, {}])

        mock_post = self._run_batch(
            wizard, return_value=_make_response(200, VALID_RESPONSE)
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('Adjunte una imagen', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 1)

    def test_batch_line_invalid_extension_sets_error(self):
        """Un .gif en la línea 1 se rechaza por ítem; la línea 2 se procesa."""
        wizard = self._batch_wizard(rows=[{'filename': 'recibo.gif'}, {}])

        mock_post = self._run_batch(
            wizard, return_value=_make_response(200, VALID_RESPONSE)
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('Formato no soportado', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 1)

    def test_batch_line_oversized_image_sets_error(self):
        """Imagen de 6 MB con límite 5 MB -> error por ítem, el lote sigue."""
        large_image = base64.b64encode(b'x' * (6 * 1024 * 1024)).decode()
        wizard = self._batch_wizard(rows=[{'image': large_image}, {}])

        mock_post = self._run_batch(
            wizard, return_value=_make_response(200, VALID_RESPONSE)
        )

        lines = self._lines(wizard)
        self.assertEqual(lines[0].status, 'error')
        self.assertIn('supera el límite', lines[0].error_message)
        self.assertEqual(lines[1].status, 'done')
        self.assertEqual(mock_post.call_count, 1)

    def test_batch_requires_configured_url(self):
        """Sin URL configurada el lote aborta con UserError antes de cualquier POST."""
        self.config.set_param('l10n_ve_digitize.url', '')
        wizard = self._batch_wizard(rows=2)

        with patch('requests.post') as mock_post, self._patch_session('sid-batch'):
            with self.assertRaises(UserError):
                wizard.action_digitize_batch()

        mock_post.assert_not_called()
        for line in self._lines(wizard):
            self.assertEqual(line.status, 'pending')

    def test_batch_requires_session(self):
        """Sin contexto HTTP (sin sid) el lote aborta con UserError y sin POST."""
        wizard = self._batch_wizard(rows=2)

        with patch('requests.post') as mock_post, \
                patch.object(digitize_client_module, 'request', None):
            with self.assertRaises(UserError) as capture:
                wizard.action_digitize_batch()

        mock_post.assert_not_called()
        self.assertIn('Sesión no detectada', str(capture.exception))

    def test_batch_builds_payload_per_line(self):
        """Cada POST lleva la imagen/nombre de su línea y el hint del wizard."""
        image_1 = _jpeg_b64(b'c')
        image_2 = _jpeg_b64(b'd')
        wizard = self._batch_wizard(
            rows=[
                {'filename': 'recibo-01.jpg', 'image': image_1},
                {'filename': 'recibo-02.PNG', 'image': image_2},
            ],
            document_type_hint='nota_credito',
        )

        mock_post = self._run_batch(
            wizard, return_value=_make_response(200, VALID_RESPONSE)
        )

        self.assertEqual(len(mock_post.call_args_list), 2)
        payloads = [call.kwargs['json'] for call in mock_post.call_args_list]
        self.assertEqual(payloads[0]['filename'], 'recibo-01.jpg')
        self.assertEqual(payloads[1]['filename'], 'recibo-02.PNG')
        self.assertEqual(payloads[0]['image_base64'], image_1)
        self.assertEqual(payloads[1]['image_base64'], image_2)
        self.assertNotIn('data:', payloads[0]['image_base64'])
        self.assertNotIn('data:', payloads[1]['image_base64'])
        self.assertEqual(payloads[0]['document_type'], 'nota_credito')
        self.assertEqual(payloads[1]['document_type'], 'nota_credito')
        headers = mock_post.call_args.kwargs['headers']
        self.assertEqual(headers['X-Odoo-Session'], 'sid-batch')

    def test_batch_merges_local_warnings_in_result_json(self):
        """result_json fusiona warnings del servicio (ganador) con los locales."""
        payload = {
            'document_type': 'factura_z',
            'confidence': 0.9,
            'extracted': {'supplier_name': 'Proveedor Lote'},
            'warnings': [
                {
                    'code': 'missing_field',
                    'field': 'supplier_rif',
                    'message': 'Advertencia del servicio',
                },
            ],
        }
        wizard = self._batch_wizard(rows=1)

        self._run_batch(wizard, return_value=_make_response(200, payload))

        line = self._lines(wizard)[0]
        self.assertEqual(line.status, 'done')
        warnings = json.loads(line.result_json)['warnings']
        keys = [(w['code'], w['field']) for w in warnings]
        self.assertEqual(keys.count(('missing_field', 'supplier_rif')), 1)
        service_warning = next(
            warning
            for warning in warnings
            if (warning['code'], warning['field']) == ('missing_field', 'supplier_rif')
        )
        self.assertEqual(service_warning['message'], 'Advertencia del servicio')
        self.assertIn(('missing_field', 'subtotal'), keys)

    def test_batch_resets_previous_results_on_reprocess(self):
        """Reprocesar: reset (pending/False/False) antes del loop; luego done."""

        def assert_reset_on_second_run(*args, **kwargs):
            # En el primer POST de la 2ª corrida el reset ya ocurrió: todas
            # las líneas deben estar pendientes y sin resultados previos.
            if assert_reset_on_second_run.calls == 0:
                for line in wizard.line_ids.read(['status', 'result_json']):
                    self.assertEqual(line['status'], 'pending')
                    self.assertFalse(line['result_json'])
            assert_reset_on_second_run.calls += 1
            return _make_response(200, VALID_RESPONSE)

        assert_reset_on_second_run.calls = 0

        wizard = self._batch_wizard(rows=2)

        self._run_batch(wizard, return_value=_make_response(200, VALID_RESPONSE))
        for line in self._lines(wizard):
            self.assertEqual(line.status, 'done')
            self.assertTrue(line.result_json)

        self._run_batch(wizard, side_effect=assert_reset_on_second_run)
        for line in self._lines(wizard):
            self.assertEqual(line.status, 'done')
            self.assertTrue(line.result_json)

    # ------------------------------------------------------------------
    # 16-21: procesamiento linea por linea desde la UI (spec 007-C)
    # ------------------------------------------------------------------
    def test_single_line_processes_only_target(self):
        """El RPC por linea procesa solo la fila pedida; las demas siguen pending."""
        wizard = self._batch_wizard(rows=2)
        lines = self._lines(wizard)

        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)) as mock_post, \
                self._patch_session('sid-line'):
            result = wizard.action_digitize_line(lines[0].id)

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result['status'], 'done')
        self.assertEqual(lines[0].status, 'done')
        self.assertEqual(lines[1].status, 'pending')

    def test_single_line_returns_error_and_keeps_next_pending(self):
        """Un timeout queda en la fila y no toca la siguiente."""
        wizard = self._batch_wizard(rows=2)
        lines = self._lines(wizard)

        with patch('requests.post', side_effect=requests.Timeout('t')), \
                self._patch_session('sid-line'):
            result = wizard.action_digitize_line(lines[0].id)

        self.assertEqual(result['status'], 'error')
        self.assertIn('tardó demasiado', result['error_message'])
        self.assertEqual(lines[0].status, 'error')
        self.assertEqual(lines[1].status, 'pending')

    def test_single_line_rejects_foreign_line(self):
        """Una linea de otro wizard no se puede procesar."""
        wizard = self._batch_wizard(rows=1)
        other = self._batch_wizard(rows=1)

        with patch('requests.post') as mock_post, self._patch_session('sid-line'):
            with self.assertRaises(UserError):
                wizard.action_digitize_line(other.line_ids.id)

        mock_post.assert_not_called()

    def test_single_line_requires_session(self):
        """Sin sesion HTTP el RPC por linea aborta sin POST y deja la fila pending."""
        wizard = self._batch_wizard(rows=1)

        with patch('requests.post') as mock_post, \
                patch.object(digitize_client_module, 'request', None):
            with self.assertRaises(UserError) as capture:
                wizard.action_digitize_line(wizard.line_ids.id)

        mock_post.assert_not_called()
        self.assertIn('Sesión no detectada', str(capture.exception))
        self.assertEqual(wizard.line_ids.status, 'pending')

    def test_single_line_reprocess_clears_previous_result(self):
        """Reprocesar una fila borra su resultado anterior antes del POST."""
        wizard = self._batch_wizard(rows=1)
        line = self._lines(wizard)[0]

        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)), \
                self._patch_session('sid-line'):
            wizard.action_digitize_line(line.id)
        self.assertEqual(line.status, 'done')
        self.assertTrue(line.result_json)

        with patch('requests.post', return_value=_make_response(503)), \
                self._patch_session('sid-line'):
            result = wizard.action_digitize_line(line.id)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(line.status, 'error')
        self.assertFalse(line.result_json)

    def test_single_line_rejects_more_than_twenty(self):
        """21 filas abortan el RPC por linea antes de cualquier POST."""
        wizard = self._batch_wizard(rows=21)

        with patch('requests.post') as mock_post, self._patch_session('sid-line'):
            with self.assertRaises(ValidationError):
                wizard.action_digitize_line(wizard.line_ids[0].id)

        mock_post.assert_not_called()

    def test_get_batch_line_ids_returns_metadata(self):
        """El runner recibe id, filename y status de cada fila."""
        wizard = self._batch_wizard(rows=2)
        lines = self._lines(wizard)

        data = wizard.get_batch_line_ids()

        self.assertEqual([row['id'] for row in data], lines.ids)
        self.assertEqual([row['status'] for row in data], ['pending', 'pending'])
        self.assertEqual(data[0]['filename'], 'recibo-01.jpg')

    # ------------------------------------------------------------------
    # 22-25: Usar datos por fila (spec 007-D)
    # ------------------------------------------------------------------
    def test_batch_line_apply_to_invoice_done(self):
        """Fila Analizado -> acción del wizard físico con defaults del fixture."""
        wizard = self._analyzed_batch()
        line = self._lines(wizard)[0]

        action = line.action_apply_line_to_invoice()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['name'], 'Factura Física Rápida')
        self.assertEqual(action['res_model'], 'l10n.ve.physical.invoice.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['view_mode'], 'form')

        context = action['context']
        self.assertEqual(context['default_type'], 'purchase')
        self.assertEqual(context['default_partner_vat'], 'J-31527189-4')
        self.assertEqual(context['default_invoice_number'], 'FAC-000123')
        self.assertEqual(context['default_control_number'], '00-000456')
        self.assertEqual(context['default_base_general'], 1000.0)
        self.assertEqual(context['default_physical_total'], 1160.0)
        self.assertEqual(context['default_digitized_document_type'], 'factura_z')
        self.assertEqual(context['default_digitize_confidence'], 0.87)

        self.assertEqual(line.status, 'done')
        self.assertEqual(wizard.state, 'draft')

    def test_batch_line_apply_to_invoice_pending(self):
        """Fila Pendiente -> UserError sin escribir nada en la fila."""
        wizard = self._batch_wizard(rows=1)
        line = self._lines(wizard)[0]

        with self.assertRaises(UserError) as capture:
            line.action_apply_line_to_invoice()

        self.assertIn('Analice el recibo', str(capture.exception))
        self.assertEqual(line.status, 'pending')
        self.assertFalse(line.result_json)

    def test_batch_line_apply_to_invoice_error(self):
        """Fila con error de análisis -> UserError."""
        wizard = self._batch_wizard(rows=2)

        self._run_batch(
            wizard,
            side_effect=[_make_response(503), _make_response(200, VALID_RESPONSE)],
        )
        line = self._lines(wizard)[0]
        self.assertEqual(line.status, 'error')

        with self.assertRaises(UserError) as capture:
            line.action_apply_line_to_invoice()

        self.assertIn('error de análisis', str(capture.exception))

    def test_batch_line_apply_to_invoice_without_result_json(self):
        """result_json ausente/corrupto/sin extracted -> UserError en 5 variantes."""
        wizard = self._batch_wizard(rows=1)
        line = self._lines(wizard)[0]
        variants = (False, 'no-json', '{}', '{"extracted": {}}', '{"extracted": null}')

        for value in variants:
            with self.subTest(result_json=value), \
                    self.assertRaises(UserError) as capture:
                line.write({'status': 'done', 'result_json': value})
                line.action_apply_line_to_invoice()

            self.assertIn('no tiene datos analizados', str(capture.exception))
