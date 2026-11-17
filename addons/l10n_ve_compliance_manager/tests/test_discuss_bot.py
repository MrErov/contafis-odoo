import base64
import json
from unittest.mock import MagicMock, patch

from odoo.addons.l10n_ve_compliance_manager.models.assistant_token import (
    verify_assistant_token,
)
from odoo.tests import TransactionCase, tagged

API_KEY = 'test-assistant-secret'


def _decode_payload(token):
    """Decodifica el payload del token sin validar la firma (solo estructura)."""
    payload_b64, _signature = token.split('.')
    padding = '=' * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode('utf-8'))


@tagged('post_install', '-at_install')
class TestDiscussBotSessionAuth(TransactionCase):
    """El bot firma un token efímero en lugar de enviar el ``sid`` (P0-04)."""

    def setUp(self):
        super().setUp()
        self.Channel = self.env['discuss.channel']
        self.User = self.env['res.users']
        self.BotUser = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        self.config_param = self.env['ir.config_parameter'].sudo()

        # Configurar webhook URL y secreto compartido del asistente
        self.config_param.set_param('l10n_ve_chat.webhook_url', 'http://localhost:8000/webhook')
        self.config_param.set_param('l10n_ve_chat.auth_token', API_KEY)

        # Usuario contador (sin api_token, ya no se usa)
        self.accountant = self.User.create({
            'name': 'Test Accountant',
            'login': 'test_accountant',
            'email': 'test@accountant.com',
        })

    def _mock_response(self, status_code=200, payload=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = payload or {'answer': 'OK', 'warnings': []}
        return response

    def _create_bot_channel(self, name):
        """Crea un canal 1-a-1 usuario/bot para los tests del bot."""
        return self.Channel.with_user(self.accountant).create({
            'name': name,
            'channel_type': 'chat',
            'channel_member_ids': [
                (0, 0, {'partner_id': self.accountant.partner_id.id}),
                (0, 0, {'partner_id': self.BotUser.partner_id.id}),
            ],
        })

    def _last_bot_message(self, channel):
        return self.env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel.id),
            ('author_id', '=', self.BotUser.partner_id.id),
        ], order='create_date DESC', limit=1)

    def test_bot_sends_signed_token_header(self):
        """El bot envía X-ContaFis-Token firmado y nunca el sid ni X-Odoo-Session."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat Token')

        with patch('requests.post', return_value=self._mock_response()) as mock_post:
            channel.with_user(self.accountant).message_post(
                body='Hola bot',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        self.assertTrue(mock_post.called, "requests.post should have been called")
        headers = mock_post.call_args.kwargs.get('headers', {})

        self.assertIn('X-ContaFis-Token', headers)
        self.assertNotIn('X-Odoo-Session', headers)
        self.assertNotIn('X-User-Token', headers)
        self.assertNotIn('Cookie', headers)
        self.assertEqual(headers.get('X-API-Key'), API_KEY)

        claims = verify_assistant_token(headers['X-ContaFis-Token'], API_KEY)
        self.assertEqual(claims.uid, self.accountant.id)
        self.assertEqual(claims.company_id, self.env.company.id)

        self.assertFalse(mock_post.call_args.kwargs['allow_redirects'])

    def test_bot_token_payload_is_minimal(self):
        """El token solo lleva uid, company_id y exp: ningún dato de sesión."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat Payload')

        with patch('requests.post', return_value=self._mock_response()) as mock_post:
            channel.with_user(self.accountant).message_post(
                body='Hola bot',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        token = mock_post.call_args.kwargs['headers']['X-ContaFis-Token']
        payload = _decode_payload(token)

        self.assertEqual(set(payload), {'uid', 'company_id', 'exp'})
        self.assertEqual(payload['uid'], self.accountant.id)
        self.assertEqual(payload['company_id'], self.env.company.id)
        self.assertGreater(payload['exp'], 0)

    def test_bot_requires_shared_secret(self):
        """Sin secreto compartido no se firma token ni se llama al webhook."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        self.config_param.set_param('l10n_ve_chat.auth_token', '')
        channel = self._create_bot_channel('Test Bot Chat Sin Secreto')

        with patch('requests.post') as mock_post:
            channel.with_user(self.accountant).message_post(
                body='Hola bot sin secreto',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        mock_post.assert_not_called()
        bot_message = self._last_bot_message(channel)
        self.assertTrue(bot_message)
        self.assertIn('secreto compartido', bot_message.body.lower())

    def test_bot_response_includes_legal_disclaimer(self):
        """La respuesta del bot debe incluir disclaimer legal."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat 2')

        with patch('requests.post', return_value=self._mock_response(
            payload={'answer': 'Respuesta técnica', 'warnings': []}
        )):
            channel.with_user(self.accountant).message_post(
                body='Pregunta fiscal',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        bot_messages = self.env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel.id),
            ('author_id', '=', self.BotUser.partner_id.id),
        ], order='create_date DESC', limit=1)

        self.assertTrue(bot_messages, "Bot should have posted a response")
        response_body = bot_messages.body

        self.assertIn('⚠️', response_body, "Response should contain warning emoji")
        self.assertIn('informativo', response_body.lower(), "Response should contain legal disclaimer")

    def test_bot_works_without_api_token(self):
        """El bot funciona aunque el usuario no tenga api_token configurado."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        user_no_token = self.User.create({
            'name': 'User No Token',
            'login': 'user_no_token',
            'email': 'no_token@test.com',
            'api_token': False,
        })

        channel = self.Channel.with_user(user_no_token).create({
            'name': 'Test Bot Chat 3',
            'channel_type': 'chat',
            'channel_member_ids': [
                (0, 0, {'partner_id': user_no_token.partner_id.id}),
                (0, 0, {'partner_id': self.BotUser.partner_id.id}),
            ],
        })

        with patch('requests.post', return_value=self._mock_response()) as mock_post:
            channel.with_user(user_no_token).message_post(
                body='Test sin token',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        self.assertTrue(mock_post.called, "Should call webhook even without api_token")
        headers = mock_post.call_args.kwargs.get('headers', {})
        self.assertNotIn('X-Odoo-Session', headers)
        claims = verify_assistant_token(headers['X-ContaFis-Token'], API_KEY)
        self.assertEqual(claims.uid, user_no_token.id)

    def test_bot_works_outside_http_context(self):
        """El token se firma sin depender de ``request`` (cron, shell, tests)."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat No HTTP')

        with patch('requests.post', return_value=self._mock_response()) as mock_post:
            channel.with_user(self.accountant).message_post(
                body='Hola bot sin request',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        self.assertTrue(mock_post.called)
        headers = mock_post.call_args.kwargs['headers']
        self.assertIn('X-ContaFis-Token', headers)

    def test_rejected_token_is_reported_as_auth_error(self):
        """Un 401/403 del agente se reporta como autenticación rechazada."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        bot_message = self._post_and_get_bot_reply('Test Bot Chat 401', 401)

        self.assertTrue(bot_message, "El bot debe responder al 401")
        body = bot_message.body.lower()
        self.assertIn('rechazó la autenticación', body)
        self.assertIn('secreto compartido', body)
        self.assertNotIn('token del webhook', body)

    def test_validation_unavailable_is_not_reported_as_agent_crash(self):
        """Un 503 (no se pudo validar el token) se distingue de un 5xx del agente."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        bot_message = self._post_and_get_bot_reply('Test Bot Chat 503', 503)

        self.assertTrue(bot_message, "El bot debe responder al 503")
        body = bot_message.body.lower()
        self.assertIn('no se pudo validar', body)
        self.assertNotIn('error del servidor del agente', body)

    def test_token_is_not_logged(self):
        """Los logs solo listan nombres de headers, nunca el token firmado."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat Logs')

        with patch('requests.post', return_value=self._mock_response()) as mock_post:
            with self.assertLogs(
                'odoo.addons.l10n_ve_compliance_manager.models', level='DEBUG'
            ) as captured:
                channel.with_user(self.accountant).message_post(
                    body='Hola bot con logs',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

        token = mock_post.call_args.kwargs['headers']['X-ContaFis-Token']
        output = '\n'.join(captured.output)
        self.assertNotIn(token, output)

    def _post_and_get_bot_reply(self, channel_name, status_code):
        """Envía un mensaje con el agente respondiendo `status_code` y devuelve la réplica del bot."""
        channel = self._create_bot_channel(channel_name)

        with patch('requests.post') as mock_post:
            mock_post.return_value = self._mock_response(
                status_code=status_code, payload={'detail': 'error'}
            )
            channel.with_user(self.accountant).message_post(
                body='Consulta con token',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        return self._last_bot_message(channel)
