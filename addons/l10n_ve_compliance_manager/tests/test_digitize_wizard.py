import base64
from unittest.mock import MagicMock, PropertyMock, patch

import odoo.addons.l10n_ve_compliance_manager.models.digitize_client as digitize_client_module
import requests
from odoo.addons.l10n_ve_compliance_manager.models.digitize_client import post_digitize
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

DIGITIZE_URL = 'http://digitize.test/digitize'

VALID_RESPONSE = {
    'document_type': 'factura_z',
    'confidence': 0.87,
    'extracted': {'supplier_name': 'Distribuidora Andina, C.A.'},
    'warnings': [],
}


def _make_response(status_code, payload=None):
    """Construye un `requests.Response` falso (cero red real)."""
    response = MagicMock()
    response.status_code = status_code
    if payload is None:
        response.json.side_effect = ValueError('Response body is not valid JSON')
    else:
        response.json.return_value = payload
    return response


class DigitizeTestMixin:
    """Helpers compartidos por las clases de test de la spec 007/T1."""

    def _patch_session(self, sid='test-session-id-123'):
        """Simula `request.session.sid` en el módulo del cliente HTTP."""
        mock_session = MagicMock()
        mock_session.sid = sid
        mock_request = MagicMock()
        type(mock_request).session = PropertyMock(return_value=mock_session)
        return patch.object(digitize_client_module, 'request', mock_request)

    def _create_wizard(self, **vals):
        defaults = {
            'type': 'purchase',
            'document_type_hint': 'auto',
            'filename': 'factura.jpg',
            'image': base64.b64encode(b'fake-jpeg-bytes').decode(),
        }
        defaults.update(vals)
        return self.env['l10n.ve.digitize.wizard'].create(defaults)


@tagged('post_install', '-at_install')
class TestDigitizeClient(DigitizeTestMixin, TransactionCase):
    """Contrato del cliente HTTP aislado hacia /digitize (RNF-02)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')

    def test_post_digitize_sends_payload_and_session_header(self):
        """El POST debe llevar el payload JSON y el header X-Odoo-Session."""
        payload = {
            'image_base64': 'ZmFrZQ==',
            'filename': 'factura.jpg',
            'document_type': 'auto',
        }
        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)) as mock_post:
            post_digitize(DIGITIZE_URL, 'sid-abc', payload, timeout=30)

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], DIGITIZE_URL)
        self.assertEqual(kwargs['json'], payload)
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json')
        self.assertEqual(kwargs['headers']['X-Odoo-Session'], 'sid-abc')
        self.assertNotIn('X-User-Token', kwargs['headers'])

    def test_post_digitize_uses_configured_timeout(self):
        """El timeout enviado a requests.post sale del parámetro configurado."""
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '12')
        wizard = self._create_wizard()

        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)) as mock_post, \
                self._patch_session():
            wizard.action_digitize()

        self.assertEqual(mock_post.call_args.kwargs['timeout'], 12.0)
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.confidence, 0.87)
        self.assertEqual(wizard.detected_document_type, 'factura_z')

    def test_post_digitize_returns_response_on_200(self):
        """Con 200 el cliente devuelve la respuesta sin interpretarla."""
        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)):
            response = post_digitize(
                DIGITIZE_URL, 'sid-abc', {'filename': 'factura.jpg'}, timeout=30
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['document_type'], 'factura_z')

    def test_post_digitize_propagates_timeout(self):
        """requests.Timeout se propaga para que el modelo decida el mensaje."""
        with patch('requests.post', side_effect=requests.Timeout('timed out')):
            with self.assertRaises(requests.Timeout):
                post_digitize(
                    DIGITIZE_URL, 'sid-abc', {'filename': 'factura.jpg'}, timeout=1
                )


@tagged('post_install', '-at_install')
class TestDigitizeWizardErrors(DigitizeTestMixin, TransactionCase):
    """Mapeo de errores del wizard de digitalización (RF-02/RF-04/RF-05/RF-12)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    def _run_with_response(self, status_code, payload=None):
        """Ejecuta action_digitize con una respuesta HTTP simulada."""
        wizard = self._create_wizard()
        with patch(
            'requests.post', return_value=_make_response(status_code, payload)
        ) as mock_post, self._patch_session():
            wizard.action_digitize()
        mock_post.assert_called_once()
        return wizard

    def test_action_digitize_requires_url(self):
        """Sin URL configurada no se llama al servicio y el wizard queda en error."""
        self.config.set_param('l10n_ve_digitize.url', '')
        wizard = self._create_wizard()

        with patch('requests.post') as mock_post, self._patch_session():
            wizard.action_digitize()

        mock_post.assert_not_called()
        self.assertEqual(wizard.state, 'error')
        self.assertIn('no está configurada', wizard.error_message)
        self.assertIn('Ajustes', wizard.error_message)

    def test_action_digitize_requires_session(self):
        """Sin contexto HTTP no hay sid: no se llama al servicio ni se lanza excepción."""
        wizard = self._create_wizard()

        with patch('requests.post') as mock_post, \
                patch.object(digitize_client_module, 'request', None):
            wizard.action_digitize()

        mock_post.assert_not_called()
        self.assertEqual(wizard.state, 'error')
        self.assertIn('Sesión no detectada', wizard.error_message)

    def test_action_digitize_builds_contract_payload(self):
        """RF-03: el wizard arma el payload del contrato sin prefijo `data:`."""
        wizard = self._create_wizard(
            image='data:image/jpeg;base64,ZmFrZQ==',
            filename='factura.JPG',
            document_type_hint='nota_credito',
        )

        with patch(
            'requests.post', return_value=_make_response(200, VALID_RESPONSE)
        ) as mock_post, self._patch_session('sid-payload'):
            wizard.action_digitize()

        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(payload['image_base64'], 'ZmFrZQ==')
        self.assertEqual(payload['filename'], 'factura.JPG')
        self.assertEqual(payload['document_type'], 'nota_credito')
        self.assertEqual(
            mock_post.call_args.kwargs['headers']['X-Odoo-Session'], 'sid-payload'
        )

    def test_action_digitize_maps_timeout_to_error(self):
        """Un timeout del servicio deja el wizard en error, sin excepción."""
        wizard = self._create_wizard()

        with patch('requests.post', side_effect=requests.Timeout('timed out')), \
                self._patch_session():
            wizard.action_digitize()

        self.assertEqual(wizard.state, 'error')
        self.assertIn('tardó demasiado', wizard.error_message)

    def test_action_digitize_maps_connection_error_to_error(self):
        """Un fallo de conexión deja el wizard en error, sin excepción."""
        wizard = self._create_wizard()

        with patch('requests.post', side_effect=requests.ConnectionError('down')), \
                self._patch_session():
            wizard.action_digitize()

        self.assertEqual(wizard.state, 'error')
        self.assertIn('No se pudo conectar', wizard.error_message)

    def test_action_digitize_maps_401_to_session_error(self):
        """401/403 = sesión de Odoo expirada, no error del servicio."""
        wizard = self._run_with_response(401)

        self.assertEqual(wizard.state, 'error')
        self.assertIn('sesión de Odoo expiró', wizard.error_message)
        self.assertNotIn('servidor', wizard.error_message.lower())

    def test_action_digitize_maps_503_to_unavailable(self):
        """503 = servicio no disponible, distinto de un 5xx del servidor."""
        wizard = self._run_with_response(503)

        self.assertEqual(wizard.state, 'error')
        self.assertIn('no está disponible', wizard.error_message)
        self.assertNotIn('Error del servidor', wizard.error_message)

    def test_action_digitize_maps_400_to_invalid_request(self):
        """400 = imagen o formato rechazado por el servicio."""
        wizard = self._run_with_response(400)

        self.assertEqual(wizard.state, 'error')
        self.assertIn('rechazado', wizard.error_message)
        self.assertNotIn('sesión', wizard.error_message.lower())

    def test_action_digitize_maps_500_to_server_error(self):
        """5xx (salvo 503) = error del servidor de digitalización."""
        wizard = self._run_with_response(500)

        self.assertEqual(wizard.state, 'error')
        self.assertIn('Error del servidor', wizard.error_message)
        self.assertNotIn('no está disponible', wizard.error_message)

    def test_action_digitize_handles_invalid_json(self):
        """Un 200 con cuerpo no-JSON deja el wizard en error, sin excepción."""
        wizard = self._run_with_response(200, payload=None)

        self.assertEqual(wizard.state, 'error')
        self.assertIn('no es JSON', wizard.error_message)

    def test_action_digitize_rejects_oversized_image(self):
        """Una imagen de 6 MB se rechaza antes de llamar al servicio."""
        large_image = base64.b64encode(b'x' * (6 * 1024 * 1024)).decode()
        wizard = self._create_wizard(image=large_image)

        with patch('requests.post') as mock_post, self._patch_session():
            with self.assertRaises(ValidationError):
                wizard.action_digitize()

        mock_post.assert_not_called()
        self.assertEqual(wizard.state, 'draft')

    def test_action_digitize_rejects_unsupported_extension(self):
        """Un .gif se rechaza antes de llamar al servicio."""
        wizard = self._create_wizard(filename='factura.gif')

        with patch('requests.post') as mock_post, self._patch_session():
            with self.assertRaises(ValidationError):
                wizard.action_digitize()

        mock_post.assert_not_called()
        self.assertEqual(wizard.state, 'draft')

    def test_action_digitize_does_not_log_image_or_session(self):
        """El log registra metadatos, nunca el base64 ni el sid (RNF-04)."""
        secret_sid = 'SECRET-SESSION-DO-NOT-LOG'
        wizard = self._create_wizard()
        image_b64 = wizard.image
        if isinstance(image_b64, bytes):
            image_b64 = image_b64.decode()

        with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)), \
                self._patch_session(secret_sid):
            with self.assertLogs(
                'odoo.addons.l10n_ve_compliance_manager.models', level='DEBUG'
            ) as captured:
                wizard.action_digitize()

        output = '\n'.join(captured.output)
        self.assertNotIn(image_b64, output)
        self.assertNotIn(secret_sid, output)
        self.assertNotIn('X-Odoo-Session', output)
        self.assertTrue(
            any('factura.jpg' in line for line in captured.output),
            'El log debe identificar el archivo analizado',
        )
        self.assertEqual(wizard.state, 'done')

    def test_menu_and_action_exist(self):
        """RF-01: el menú de Impuestos abre el wizard de digitalización."""
        action = self.env.ref('l10n_ve_compliance_manager.action_l10n_ve_digitize_wizard')
        self.assertEqual(action.res_model, 'l10n.ve.digitize.wizard')
        self.assertEqual(action.target, 'new')

        view = self.env.ref('l10n_ve_compliance_manager.view_l10n_ve_digitize_wizard_form')
        self.assertEqual(view.model, 'l10n.ve.digitize.wizard')

        menu = self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_digitize')
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(
            menu.parent_id,
            self.env.ref('l10n_ve_compliance_manager.menu_l10n_ve_compliance_taxes'),
        )
        self.assertEqual(menu.sequence, 60)
