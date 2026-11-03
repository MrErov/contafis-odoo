import base64
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import odoo.addons.l10n_ve_compliance_manager.models.digitize_client as digitize_client_module
import requests
from odoo.addons.l10n_ve_compliance_manager.models.digitize_client import post_digitize
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

DIGITIZE_URL = 'http://digitize.test/digitize'
FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _load_fixture(name='digitize_response_200.json'):
    """Carga una respuesta realista del servicio desde ``tests/fixtures``."""
    with (FIXTURES_DIR / name).open(encoding='utf-8') as handle:
        return json.load(handle)


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

    def test_timeout_is_floored_to_one_second(self):
        """Un timeout configurado en 0 o negativo se eleva a 1 segundo."""
        wizard = self._create_wizard()
        for configured in ('0', '-5'):
            self.config.set_param('l10n_ve_digitize.timeout_seconds', configured)
            self.assertEqual(wizard._get_timeout(), 1.0)

    def test_get_image_base64_encodes_raw_bytes(self):
        """Bytes no-ASCII (JPEG crudo) se codifican en base64, no se descartan."""
        raw = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        wizard = self._create_wizard(image=raw)

        self.assertEqual(
            wizard._get_image_base64(), base64.b64encode(raw).decode('ascii')
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

    def test_parse_response_tolerates_malformed_optional_parts(self):
        """`_parse_response` tolera `confidence` inválida y `warnings` no-lista."""
        wizard = self._run_with_response(
            200,
            {
                'document_type': 'factura_z',
                'confidence': None,
                'extracted': [],
            },
        )
        self.assertEqual(wizard.state, 'error')
        self.assertIn('incompleta', wizard.error_message)

        payload = _load_fixture()
        payload['warnings'] = {'code': 'missing_field'}
        wizard = self._run_with_response(200, payload)

        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.warnings_json, '[]')

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

    def test_action_digitize_accepts_uppercase_extension(self):
        """Extensiones en mayúsculas (JPG, JPEG, PNG, WEBP) se aceptan."""
        for ext in ('JPG', 'JPEG', 'PNG', 'WEBP'):
            with self.subTest(ext=ext):
                wizard = self._create_wizard(filename=f'factura.{ext}')
                with patch('requests.post', return_value=_make_response(200, VALID_RESPONSE)) as mock_post, \
                        self._patch_session():
                    wizard.action_digitize()
                # El servicio se llama (no hay error de validación)
                mock_post.assert_called_once()
                self.assertEqual(wizard.state, 'done')

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


@tagged('post_install', '-at_install')
class TestDigitizeMapping(DigitizeTestMixin, TransactionCase):
    """Mapeo de datos extraídos al wizard de Factura Física Rápida (RF-09/10/11/17)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    def _done_wizard(self, payload=None):
        """Ejecuta la digitalización con una respuesta simulada y la deja en `done`."""
        wizard = self._create_wizard()
        with patch(
            'requests.post',
            return_value=_make_response(200, payload or _load_fixture()),
        ), self._patch_session():
            wizard.action_digitize()
        self.assertEqual(wizard.state, 'done')
        return wizard

    def _map(self, extracted):
        return self._create_wizard()._map_extracted_to_invoice_defaults(extracted)

    def _warning_keys(self, extracted):
        wizard = self._create_wizard()
        return [
            (warning['code'], warning['field'])
            for warning in wizard._build_local_warnings(extracted)
        ]

    def test_apply_returns_physical_wizard_action_with_defaults(self):
        """RF-09: desde `done` el botón abre el wizard de factura física prellenado."""
        wizard = self._done_wizard()
        action = wizard.action_apply_to_invoice()

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

        # Vista previa persistida en `done` (RF-06).
        self.assertEqual(wizard.supplier_name, 'Distribuidora Andina, C.A.')
        self.assertEqual(wizard.supplier_rif, 'J-31527189-4')
        self.assertEqual(wizard.invoice_number, 'FAC-000123')
        self.assertEqual(wizard.currency_code, 'VES')
        self.assertEqual(wizard.subtotal, 1000.0)
        self.assertEqual(wizard.iva_rate, 0.16)
        self.assertEqual(wizard.iva_amount, 160.0)
        self.assertEqual(wizard.igtf_amount, 0.0)
        self.assertEqual(wizard.total, 1160.0)
        self.assertEqual(
            json.loads(wizard.extracted_json)['supplier_rif'], 'J-31527189-4'
        )

        draft_wizard = self._create_wizard()
        with self.assertRaises(UserError):
            draft_wizard.action_apply_to_invoice()

    def test_maps_general_rate_to_base_general(self):
        """RF-10: IVA 16 % llena `base_general` con el subtotal."""
        defaults = self._map({'subtotal': 1000.0, 'iva_rate': 0.16})

        self.assertEqual(defaults['default_base_general'], 1000.0)
        self.assertNotIn('default_base_reduced', defaults)
        self.assertNotIn('default_base_additional', defaults)
        self.assertNotIn('default_base_not_taxed', defaults)

        additional = self._map({'subtotal': 100.0, 'iva_rate': 0.2})
        self.assertEqual(additional['default_base_additional'], 100.0)

        odd_rate = self._map({'subtotal': 100.0, 'iva_rate': 0.1})
        self.assertNotIn('default_base_general', odd_rate)
        self.assertNotIn('default_base_reduced', odd_rate)
        self.assertIn(('parsing_error', 'iva_rate'), self._warning_keys({'iva_rate': 0.1}))

        over_hundred = self._map({'subtotal': 100.0, 'iva_rate': 1.2})
        self.assertNotIn('default_base_additional', over_hundred)
        self.assertIn(('parsing_error', 'iva_rate'), self._warning_keys({'iva_rate': 1.2}))

    def test_maps_reduced_rate_to_base_reduced(self):
        """RF-10: IVA 8 % llena `base_reduced` con el subtotal."""
        defaults = self._map({'subtotal': 500.0, 'iva_rate': 0.08})

        self.assertEqual(defaults['default_base_reduced'], 500.0)
        self.assertNotIn('default_base_general', defaults)

    def test_maps_zero_rate_to_base_not_taxed(self):
        """RF-10: IVA 0 % llena `base_not_taxed`, no `base_general`."""
        defaults = self._map({'subtotal': 250.0, 'iva_rate': 0.0})

        self.assertEqual(defaults['default_base_not_taxed'], 250.0)
        self.assertNotIn('default_base_general', defaults)

        zero_subtotal = self._map({'subtotal': 0.0, 'iva_rate': 0.16})
        self.assertNotIn('default_base_general', zero_subtotal)

    def test_maps_usd_currency(self):
        """RF-10: VES usa la moneda de la compañía y USD el dólar configurado."""
        usd = self.env['res.currency'].search(
            [('name', '=', 'USD'), ('active', 'in', [True, False])], limit=1
        )
        if not usd:
            usd = self.env['res.currency'].create({'name': 'USD', 'symbol': '$'})

        self.assertEqual(self._map({'currency': 'USD'})['default_currency_id'], usd.id)
        self.assertEqual(
            self._map({'currency': 'VES'})['default_currency_id'],
            self.env.company.currency_id.id,
        )

    def test_maps_dates_and_numbers(self):
        """RF-10: fechas como `date`, números y RIF copiados tal cual."""
        extracted = _load_fixture()['extracted']
        defaults = self._map(extracted)

        self.assertIsInstance(defaults['default_invoice_date'], date)
        self.assertIsInstance(defaults['default_invoice_date_due'], date)
        self.assertEqual(defaults['default_invoice_date'], date(2026, 8, 15))
        self.assertEqual(defaults['default_invoice_date_due'], date(2026, 9, 15))
        self.assertEqual(defaults['default_invoice_number'], 'FAC-000123')
        self.assertEqual(defaults['default_control_number'], '00-000456')
        self.assertEqual(defaults['default_partner_vat'], 'J-31527189-4')
        self.assertEqual(
            defaults['default_new_partner_name'], 'Distribuidora Andina, C.A.'
        )

        invalid = self._map({'invoice_date': 'not-a-date'})
        self.assertFalse(invalid['default_invoice_date'])
        self.assertIn(
            ('parsing_error', 'invoice_date'),
            self._warning_keys({'invoice_date': 'not-a-date'}),
        )

        # `invoice_date_due` no es obligatoria: ausente no advierte, inválida sí.
        no_due = self._map({'due_date': None})
        self.assertFalse(no_due['default_invoice_date_due'])
        self.assertNotIn(
            ('missing_field', 'due_date'), self._warning_keys({'due_date': None})
        )
        self.assertIn(
            ('parsing_error', 'due_date'),
            self._warning_keys({'due_date': 'not-a-date'}),
        )

    def test_apply_does_not_default_invoice_date_to_today(self):
        """RF-11: sin fecha extraída no se hereda la fecha de hoy del destino."""
        payload = _load_fixture()
        payload['extracted'].pop('invoice_date')
        wizard = self._done_wizard(payload)

        action = wizard.action_apply_to_invoice()
        self.assertFalse(action['context']['default_invoice_date'])

        defaults = self.env['l10n.ve.physical.invoice.wizard'].with_context(
            **action['context']
        ).default_get(['invoice_date'])
        self.assertFalse(defaults['invoice_date'])

    def test_maps_concept_from_lines(self):
        """RF-10: las descripciones se unen y se recortan a 255 caracteres."""
        defaults = self._map(
            {'lines': [{'description': 'A'}, {'description': 'B'}]}
        )
        self.assertEqual(defaults['default_concept'], 'A / B')

        truncated = self._map({'lines': [{'description': 'x' * 300}]})
        self.assertEqual(len(truncated['default_concept']), 255)

        empty = self._map({'lines': []})
        self.assertNotIn('default_concept', empty)

    def test_matches_existing_partner_by_rif(self):
        """RF-17: un RIF válido de la compañía activa resuelve el partner."""
        rif = 'V-12345678-5'
        partner = self.env['res.partner'].create(
            {'name': 'Proveedor Mapeo', 'vat': rif}
        )

        defaults = self._map({'supplier_rif': rif, 'supplier_name': 'Proveedor Mapeo'})

        self.assertEqual(defaults['default_partner_id'], partner.id)
        self.assertEqual(defaults['default_partner_vat'], rif)
        self.assertEqual(defaults['default_new_partner_name'], 'Proveedor Mapeo')

        # RIF válido sin partner: se carga el RIF pero no se inventa el partner.
        unmatched = self._map({'supplier_rif': 'J-98765432-5'})
        self.assertNotIn('default_partner_id', unmatched)
        self.assertEqual(unmatched['default_partner_vat'], 'J-98765432-5')

    def test_partner_from_other_company_is_not_reused(self):
        """RF-17: un partner de otra compañía no se reutiliza por coincidencia de RIF."""
        rif = 'G-87654321-4'  # RIF válido (módulo 11).
        other_company = self.env['res.company'].sudo().create(
            {'name': 'Otra Compañía Digitalización'}
        )
        self.env['res.partner'].sudo().create(
            {
                'name': 'Proveedor Otra Compañía',
                'vat': rif,
                'company_id': other_company.id,
            }
        )

        defaults = self._map({'supplier_rif': rif})

        self.assertNotIn('default_partner_id', defaults)
        self.assertEqual(defaults['default_partner_vat'], rif)

    def test_invalid_rif_is_warned_and_partner_left_empty(self):
        """RF-11: RIF inválido se conserva como dato y se advierte, sin partner."""
        rif = 'J-12345678-9'  # Dígito de control incorrecto.

        defaults = self._map({'supplier_rif': rif, 'supplier_name': 'Proveedor Inválido'})

        self.assertNotIn('default_partner_id', defaults)
        self.assertEqual(defaults['default_partner_vat'], rif)
        self.assertEqual(defaults['default_new_partner_name'], 'Proveedor Inválido')

        invalid = [
            warning
            for warning in self._create_wizard()._build_local_warnings(
                {'supplier_rif': rif}
            )
            if warning['code'] == 'invalid_rif'
        ]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]['field'], 'supplier_rif')
        self.assertEqual(invalid[0]['extracted_value'], rif)

    def test_missing_amounts_do_not_raise(self):
        """RF-11: sin subtotal ni tasa no se emiten bases y se advierte."""
        extracted = {'subtotal': None, 'iva_rate': None}
        defaults = self._map(extracted)

        for key in (
            'default_base_general',
            'default_base_reduced',
            'default_base_additional',
            'default_base_not_taxed',
        ):
            self.assertNotIn(key, defaults)

        warning_keys = self._warning_keys(extracted)
        self.assertIn(('missing_field', 'subtotal'), warning_keys)
        self.assertIn(('missing_field', 'iva_rate'), warning_keys)
        self.assertIn(('missing_field', 'supplier_name'), warning_keys)

    def test_digitize_persists_local_warnings(self):
        """`action_digitize` persiste las advertencias locales fusionadas (RF-11)."""
        payload = {
            'document_type': 'factura_z',
            'confidence': 0.9,
            'extracted': {'supplier_name': 'Proveedor Sin RIF'},
            'warnings': [
                {
                    'code': 'missing_field',
                    'field': 'supplier_rif',
                    'message': 'Advertencia del servicio',
                }
            ],
        }
        wizard = self._done_wizard(payload)

        warnings = json.loads(wizard.warnings_json)
        warning_keys = [(warning['code'], warning['field']) for warning in warnings]

        # La colisión (missing_field, supplier_rif) conserva la del servicio.
        self.assertEqual(warning_keys.count(('missing_field', 'supplier_rif')), 1)
        service_warning = next(
            warning
            for warning in warnings
            if (warning['code'], warning['field'])
            == ('missing_field', 'supplier_rif')
        )
        self.assertEqual(service_warning['message'], 'Advertencia del servicio')

        # Una advertencia solo local también queda persistida.
        self.assertIn(('missing_field', 'invoice_number'), warning_keys)


@tagged('post_install', '-at_install', 'digitize_warnings_ui')
class TestDigitizeWarningsUi(DigitizeTestMixin, TransactionCase):
    """UI de confianza, advertencias y líneas extraídas (T3 - RF-06, RF-07, RF-08)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    def _done_wizard(self, payload=None):
        """Ejecuta la digitalización con una respuesta simulada y la deja en `done`."""
        wizard = self._create_wizard()
        with patch(
            'requests.post',
            return_value=_make_response(200, payload or _load_fixture()),
        ), self._patch_session():
            wizard.action_digitize()
        self.assertEqual(wizard.state, 'done')
        return wizard

    def test_confidence_pct_computed(self):
        """confidence_pct = confidence * 100 redondeado a int (ej: 0.87 -> 87)."""
        base_payload = _load_fixture()
        for conf, expected in [(0.87, 87), (0.60, 60), (0.50, 50), (0.0, 0)]:
            payload = dict(base_payload)
            payload['confidence'] = conf
            w = self._done_wizard(payload)
            self.assertEqual(w.confidence_pct, expected, f"confidence={conf}")

    def test_has_warnings_flag(self):
        """has_warnings = True cuando hay warnings; False cuando no."""
        wizard = self._done_wizard()  # fixture sin warnings
        self.assertFalse(wizard.has_warnings)

        payload = _load_fixture()
        payload['warnings'] = [{'code': 'missing_field', 'field': 'supplier_rif', 'message': 'Falta RIF'}]
        wizard = self._done_wizard(payload)
        self.assertTrue(wizard.has_warnings)

    def test_warnings_text_lists_every_code(self):
        """Los 6 códigos del contrato aparecen en warnings_text."""
        base_payload = _load_fixture()
        payload = dict(base_payload)
        payload['warnings'] = [
            {'code': 'low_confidence', 'message': 'msg1', 'field': 'control_number'},
            {'code': 'invalid_rif', 'message': 'msg2', 'field': 'supplier_rif'},
            {'code': 'amount_mismatch', 'message': 'msg3', 'field': 'total'},
            {'code': 'missing_field', 'message': 'msg4', 'field': 'invoice_date'},
            {'code': 'unknown_document_type', 'message': 'msg5', 'field': None},
            {'code': 'parsing_error', 'message': 'msg6', 'field': 'subtotal'},
        ]
        wizard = self._done_wizard(payload)
        text = wizard.warnings_text
        for code in ('low_confidence', 'invalid_rif', 'amount_mismatch',
                     'missing_field', 'unknown_document_type', 'parsing_error'):
            self.assertIn(f'{code}:', text)

    def test_warning_text_is_plain_text(self):
        """warnings_text no contiene markup HTML (ni < ni > sin escapar)."""
        base_payload = _load_fixture()
        payload = dict(base_payload)
        payload['warnings'] = [
            {'code': 'low_confidence', 'message': '<script>alert(1)</script>', 'field': 'x'},
        ]
        wizard = self._done_wizard(payload)
        text = wizard.warnings_text
        self.assertNotIn('<', text)
        self.assertNotIn('>', text)
        self.assertIn('low_confidence:', text)

    def test_line_preview_rows_created(self):
        """Dos líneas en la respuesta -> dos registros digitize_line_ids."""
        payload = _load_fixture()  # tiene 2 líneas
        wizard = self._done_wizard(payload)
        self.assertEqual(len(wizard.digitize_line_ids), 2)
        self.assertEqual(wizard.digitize_line_ids[0].description, 'Servicio de consultoría')
        self.assertEqual(wizard.digitize_line_ids[1].quantity, 2)

    def test_total_mismatch_flag_true_when_difference(self):
        """total_mismatch = True cuando total != subtotal + iva_amount (tolerancia 0.01)."""
        # Caso OK: 1000 + 160 = 1160
        wizard = self._done_wizard()
        self.assertFalse(wizard.total_mismatch)

        # Caso descuadre: 1000 + 160 != 1200
        payload = _load_fixture()
        payload['extracted']['total'] = 1200.0
        wizard = self._done_wizard(payload)
        self.assertTrue(wizard.total_mismatch)

        # IGTF NO cuenta para mismatch: 1000 + 160 + 30(IGTF) = 1190 != 1160 -> mismatch por IGTF no debe activarse
        payload = _load_fixture()
        payload['extracted']['igtf_amount'] = 30.0
        payload['extracted']['total'] = 1190.0  # subtotal + iva + igtf
        wizard = self._done_wizard(payload)
        self.assertFalse(wizard.total_mismatch)


@tagged('post_install', '-at_install')
class TestDigitizeDocumentTypes(DigitizeTestMixin, TransactionCase):
    """Propagación de tipo de documento digitalizado (NC/ND) al wizard físico (RF-13, RF-14)."""

    def setUp(self):
        super().setUp()
        self.config = self.env['ir.config_parameter'].sudo()
        self.config.set_param('l10n_ve_digitize.url', DIGITIZE_URL)
        self.config.set_param('l10n_ve_digitize.timeout_seconds', '30')
        self.config.set_param('l10n_ve_digitize.max_image_mb', '5')

    def _map_defaults(self, extracted, type='purchase'):
        """Helper: llama al método de mapeo y retorna los defaults."""
        wizard = self._create_wizard(type=type)
        # Set confidence on wizard (normally set by action_digitize)
        wizard.confidence = extracted.get('confidence', 0.0)
        return wizard._map_extracted_to_invoice_defaults(extracted)

    def test_credit_note_purchase_creates_refund(self):
        """NC de compra -> default_digitized_document_type='nota_credito', confidence, ref."""
        extracted = {
            'document_type': 'nota_credito',
            'confidence': 0.92,
            'supplier_rif': 'J-31527189-4',
            'supplier_name': 'Proveedor NC',
            'invoice_number': 'NC-001',
            'control_number': 'CTRL-NC-001',
            'credit_note_ref': 'FAC-ORIGINAL-001',
            'currency': 'VES',
            'subtotal': 500.0,
            'iva_rate': 0.16,
            'total': 580.0,
        }
        defaults = self._map_defaults(extracted, type='purchase')

        self.assertEqual(defaults.get('default_digitized_document_type'), 'nota_credito')
        self.assertEqual(defaults.get('default_digitize_confidence'), 0.92)
        self.assertEqual(defaults.get('default_digitized_document_ref'), 'FAC-ORIGINAL-001')

    def test_credit_note_sale_creates_refund(self):
        """NC de venta -> mismo tipo, misma ref."""
        extracted = {
            'document_type': 'nota_credito',
            'confidence': 0.88,
            'supplier_rif': 'J-31527189-4',
            'supplier_name': 'Cliente NC',
            'invoice_number': 'NC-002',
            'control_number': 'CTRL-NC-002',
            'credit_note_ref': 'FAC-VENTA-005',
            'currency': 'VES',
            'subtotal': 300.0,
            'iva_rate': 0.16,
            'total': 348.0,
        }
        defaults = self._map_defaults(extracted, type='sale')

        self.assertEqual(defaults.get('default_digitized_document_type'), 'nota_credito')
        self.assertEqual(defaults.get('default_digitize_confidence'), 0.88)
        self.assertEqual(defaults.get('default_digitized_document_ref'), 'FAC-VENTA-005')

    def test_credit_note_uses_credit_note_ref(self):
        """NC usa credit_note_ref, no debit_note_ref."""
        extracted = {
            'document_type': 'nota_credito',
            'confidence': 0.90,
            'credit_note_ref': 'FAC-CREDITO-123',
            'debit_note_ref': 'FAC-DEBITO-456',  # no debe usarse
        }
        defaults = self._map_defaults(extracted)

        self.assertEqual(defaults.get('default_digitized_document_ref'), 'FAC-CREDITO-123')

    def test_debit_note_creates_invoice_with_ref(self):
        """ND -> default_digitized_document_type='nota_debito', usa debit_note_ref."""
        extracted = {
            'document_type': 'nota_debito',
            'confidence': 0.91,
            'supplier_rif': 'J-31527189-4',
            'supplier_name': 'Proveedor ND',
            'invoice_number': 'ND-001',
            'control_number': 'CTRL-ND-001',
            'debit_note_ref': 'FAC-ORIGINAL-002',
            'currency': 'VES',
            'subtotal': 200.0,
            'iva_rate': 0.16,
            'total': 232.0,
        }
        defaults = self._map_defaults(extracted)

        self.assertEqual(defaults.get('default_digitized_document_type'), 'nota_debito')
        self.assertEqual(defaults.get('default_digitize_confidence'), 0.91)
        self.assertEqual(defaults.get('default_digitized_document_ref'), 'FAC-ORIGINAL-002')

    def test_unknown_document_type_falls_back(self):
        """Tipo desconocido -> no emite defaults digitalizados (guarda compatibilidad)."""
        extracted = {
            'document_type': 'otro_documento',
            'confidence': 0.50,
            'credit_note_ref': 'REF-XXX',
        }
        defaults = self._map_defaults(extracted)

        self.assertNotIn('default_digitized_document_type', defaults)
        self.assertNotIn('default_digitize_confidence', defaults)
        self.assertNotIn('default_digitized_document_ref', defaults)
