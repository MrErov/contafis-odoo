from unittest.mock import MagicMock, PropertyMock, patch

import odoo.addons.l10n_ve_compliance_manager.models.discuss_channel as discuss_channel_module
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDiscussBotSessionAuth(TransactionCase):
    """Tests para autenticación por sesión en el bot de Discuss (Spec 006 T1)."""

    def setUp(self):
        super().setUp()
        self.Channel = self.env['discuss.channel']
        self.User = self.env['res.users']
        self.BotUser = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        self.config_param = self.env['ir.config_parameter'].sudo()

        # Configurar webhook URL
        self.config_param.set_param('l10n_ve_chat.webhook_url', 'http://localhost:8000/webhook')

        # Usuario contador (sin api_token, ya no se usa)
        self.accountant = self.User.create({
            'name': 'Test Accountant',
            'login': 'test_accountant',
            'email': 'test@accountant.com',
        })

    def test_bot_sends_x_odoo_session_header(self):
        """El bot debe enviar header X-Odoo-Session en lugar de X-User-Token."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        # Crear canal 1-a-1 con el bot
        channel = self.Channel.with_user(self.accountant).create({
            'name': 'Test Bot Chat',
            'channel_type': 'chat',
            'channel_member_ids': [
                (0, 0, {'partner_id': self.accountant.partner_id.id}),
                (0, 0, {'partner_id': self.BotUser.partner_id.id}),
            ],
        })

        # Mock requests.post para capturar headers
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'answer': 'Respuesta del bot', 'warnings': []}
            mock_post.return_value = mock_response

            # Mock request.session.sid on the module
            mock_session = MagicMock()
            mock_session.sid = 'test-session-id-123'
            mock_request = MagicMock()
            type(mock_request).session = PropertyMock(return_value=mock_session)
            original_request = discuss_channel_module.request
            discuss_channel_module.request = mock_request

            try:
                # Enviar mensaje como contador
                channel.with_user(self.accountant).message_post(
                    body='Hola bot',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

                # Verificar que requests.post fue llamado
                self.assertTrue(mock_post.called, "requests.post should have been called")

                # Obtener headers enviados
                call_args = mock_post.call_args
                headers = call_args.kwargs.get('headers', {})

                # Verificar header X-Odoo-Session presente
                self.assertIn('X-Odoo-Session', headers, "Header X-Odoo-Session should be present")

                # Verificar que NO se envía X-User-Token (legacy)
                self.assertNotIn('X-User-Token', headers, "Header X-User-Token should not be sent")

                # Verificar que el valor del session ID es el esperado
                session_header = headers['X-Odoo-Session']
                self.assertEqual(session_header, 'test-session-id-123', "X-Odoo-Session should match mocked session ID")
            finally:
                discuss_channel_module.request = original_request

    def test_bot_response_includes_legal_disclaimer(self):
        """La respuesta del bot debe incluir disclaimer legal."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self.Channel.with_user(self.accountant).create({
            'name': 'Test Bot Chat 2',
            'channel_type': 'chat',
            'channel_member_ids': [
                (0, 0, {'partner_id': self.accountant.partner_id.id}),
                (0, 0, {'partner_id': self.BotUser.partner_id.id}),
            ],
        })

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'answer': 'Respuesta técnica', 'warnings': []}
            mock_post.return_value = mock_response

            # Mock request.session.sid on the module
            mock_session = MagicMock()
            mock_session.sid = 'test-session-id-123'
            mock_request = MagicMock()
            type(mock_request).session = PropertyMock(return_value=mock_session)
            original_request = discuss_channel_module.request
            discuss_channel_module.request = mock_request

            try:
                channel.with_user(self.accountant).message_post(
                    body='Pregunta fiscal',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

                # Obtener el mensaje de respuesta del bot (último mensaje en el canal)
                bot_messages = self.env['mail.message'].search([
                    ('model', '=', 'discuss.channel'),
                    ('res_id', '=', channel.id),
                    ('author_id', '=', self.BotUser.partner_id.id),
                ], order='create_date DESC', limit=1)

                self.assertTrue(bot_messages, "Bot should have posted a response")
                response_body = bot_messages.body

                # Verificar disclaimer legal presente
                self.assertIn('⚠️', response_body, "Response should contain warning emoji")
                self.assertIn('informativo', response_body.lower(), "Response should contain legal disclaimer")
            finally:
                discuss_channel_module.request = original_request

    def test_bot_works_without_api_token(self):
        """El bot debe funcionar aunque el usuario no tenga api_token configurado."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        # Usuario SIN api_token
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

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'answer': 'OK', 'warnings': []}
            mock_post.return_value = mock_response

            # Mock request.session.sid on the module
            mock_session = MagicMock()
            mock_session.sid = 'test-session-id-456'
            mock_request = MagicMock()
            type(mock_request).session = PropertyMock(return_value=mock_session)
            original_request = discuss_channel_module.request
            discuss_channel_module.request = mock_request

            try:
                # NO debe lanzar error por token vacío
                channel.with_user(user_no_token).message_post(
                    body='Test sin token',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

                self.assertTrue(mock_post.called, "Should call webhook even without api_token")
                headers = mock_post.call_args.kwargs.get('headers', {})
                self.assertIn('X-Odoo-Session', headers)
                self.assertEqual(headers['X-Odoo-Session'], 'test-session-id-456')
            finally:
                discuss_channel_module.request = original_request

    def _create_bot_channel(self, name):
        """Crea un canal 1-a-1 usuario/bot para los tests de blindaje."""
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

    def test_no_http_context_posts_friendly_session_message(self):
        """Fuera de contexto HTTP (request = None) no debe fallar ni llamar al webhook."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat No HTTP')

        original_request = discuss_channel_module.request
        discuss_channel_module.request = None

        try:
            with patch('requests.post') as mock_post:
                channel.with_user(self.accountant).message_post(
                    body='Hola bot sin contexto HTTP',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                self.assertFalse(
                    mock_post.called,
                    "No debe llamarse al webhook sin session_id",
                )
        finally:
            discuss_channel_module.request = original_request

        bot_message = self._last_bot_message(channel)
        self.assertTrue(bot_message, "El bot debe dejar constancia del fallo de sesión")
        self.assertIn('Sesión no detectada', bot_message.body)

    def test_unbound_request_does_not_raise(self):
        """Si el acceso a request.session lanza, se captura y se avisa al usuario."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        channel = self._create_bot_channel('Test Bot Chat Unbound Request')

        mock_request = MagicMock()
        type(mock_request).session = PropertyMock(
            side_effect=RuntimeError('object is not bound to a request')
        )

        original_request = discuss_channel_module.request
        discuss_channel_module.request = mock_request

        try:
            with patch('requests.post') as mock_post:
                channel.with_user(self.accountant).message_post(
                    body='Hola bot con request roto',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                self.assertFalse(
                    mock_post.called,
                    "No debe llamarse al webhook si no hay session_id",
                )
        finally:
            discuss_channel_module.request = original_request

        bot_message = self._last_bot_message(channel)
        self.assertTrue(bot_message, "El bot debe postear el aviso de sesión")
        self.assertIn('Sesión no detectada', bot_message.body)

    def _post_and_get_bot_reply(self, channel_name, status_code):
        """Envía un mensaje con el agente respondiendo `status_code` y devuelve la réplica del bot."""
        channel = self._create_bot_channel(channel_name)

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.json.return_value = {'detail': 'error'}
            mock_post.return_value = mock_response

            mock_session = MagicMock()
            mock_session.sid = 'test-session-id-789'
            mock_request = MagicMock()
            type(mock_request).session = PropertyMock(return_value=mock_session)
            original_request = discuss_channel_module.request
            discuss_channel_module.request = mock_request

            try:
                channel.with_user(self.accountant).message_post(
                    body='Consulta con sesión',
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            finally:
                discuss_channel_module.request = original_request

        return self._last_bot_message(channel)

    def test_expired_session_is_reported_as_session_error(self):
        """Un 401 del agente (sesión expirada) no debe hablar del token del webhook."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        bot_message = self._post_and_get_bot_reply('Test Bot Chat 401', 401)

        self.assertTrue(bot_message, "El bot debe responder al 401")
        body = bot_message.body.lower()
        self.assertIn('sesión de odoo expiró', body)
        self.assertIn('recargá odoo', body)
        self.assertNotIn('token del webhook', body)

    def test_validation_unavailable_is_not_reported_as_agent_crash(self):
        """Un 503 (no se pudo validar la sesión) se distingue de un 5xx del agente."""
        if not self.BotUser:
            self.skipTest("Bot user not found")

        bot_message = self._post_and_get_bot_reply('Test Bot Chat 503', 503)

        self.assertTrue(bot_message, "El bot debe responder al 503")
        body = bot_message.body.lower()
        self.assertIn('no se pudo validar', body)
        self.assertNotIn('error del servidor del agente', body)
