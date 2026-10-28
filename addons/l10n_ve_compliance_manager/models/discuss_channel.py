import logging

import requests
from odoo import models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def _is_contafis_bot_channel(self, author_id):
        """Check if the message is from a user to the ContaFis bot."""
        bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        if not bot_user:
            return False
        bot_partner_id = bot_user.partner_id.id
        # Check if this is a 1-on-1 channel with the bot
        if self.channel_type == 'chat':
            partners = self.channel_member_ids.mapped('partner_id')
            return bot_partner_id in partners.ids and len(partners) == 2
        return False

    def message_post(self, **kwargs):
        """Override message_post to intercept messages to the bot."""
        # Get the message body and author
        body = kwargs.get('body', '')
        author_id = kwargs.get('author_id') or self.env.user.partner_id.id

        # Call parent to post the message first
        message = super().message_post(**kwargs)

        bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        if not bot_user:
            return message

        bot_partner_id = bot_user.partner_id.id

        # Skip messages sent by the bot itself (prevent infinite loop)
        if author_id == bot_partner_id:
            return message

        # Only intercept in 1-on-1 channels with the bot
        if not self._is_contafis_bot_channel(author_id):
            return message

        # Resolve the sender: prefer env.user, fallback to partner lookup
        if self.env.user and self.env.user.partner_id.id == author_id:
            user = self.env.user
        else:
            user = self.env['res.users'].search([
                ('partner_id', '=', author_id)
            ], limit=1)

        if not user:
            _logger.warning("Message from partner without user: %s", author_id)
            self._post_bot_error(_("⚠️ No se puede identificar tu usuario para procesar la consulta."))
            return message

        # Check API token
        if not user.api_token:
            self._post_bot_error(_("⚠️ Por favor, configura tu Token API en tus preferencias para usar el Asistente."))
            return message

        # Call the webhook with the user context
        try:
            response_data = self._call_webhook(user, body, self.id)
            if response_data:
                self._post_bot_response(response_data)
        except Exception as e:
            _logger.error("Error calling webhook: %s", e)
            self._post_bot_error(_("Error al comunicarse con el agente externo. Verifique la configuración."))

        return message

    def _is_configured(self):
        """Check if the webhook is configured."""
        webhook_url = self.env['ir.config_parameter'].sudo().get_param('l10n_ve_chat.webhook_url', '')
        return bool(webhook_url)

    def _post_bot_error(self, msg):
        """Post an error/warning message as the bot."""
        bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        if bot_user:
            self.sudo().message_post(
                body=msg,
                author_id=bot_user.partner_id.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def _call_webhook(self, user, question, channel_id):
        """Call the configured webhook with the user's question."""
        if not self._is_configured():
            # Post a configuration warning as the bot
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("⚠️ El Asistente de IA no está configurado. Ve a Ajustes > General > Asistente de IA y pega la URL de tu agente (n8n, LangChain, OpenAI, etc.)."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None

        webhook_url = self.env['ir.config_parameter'].sudo().get_param('l10n_ve_chat.webhook_url', '')
        auth_token = self.env['ir.config_parameter'].sudo().get_param('l10n_ve_chat.auth_token', '')

        # company = user.company_id or self.env.company  # unused
        _company = user.company_id or self.env.company  # unused, kept for clarity

        # Get conversation history for context
        history = self._get_conversation_history(channel_id)

        payload = {
            'question': question,
            'conversation_id': str(channel_id),
            'history': history,
        }
        headers = {
            'Content-Type': 'application/json',
        }
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        try:
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=30)
        except requests.Timeout:
            _logger.error("Timeout calling webhook: %s", webhook_url)
            # Post timeout error as bot
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("⏱️ Timeout al comunicarse con el agente. Reintente en unos minutos."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None
        except requests.RequestException as e:
            _logger.error("Request error: %s", e)
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("❌ Error de comunicación con el agente. Verifique la URL del webhook."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None

        if response.status_code == 401 or response.status_code == 403:
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("🔐 Error de autenticación con el agente. Verifique el token del webhook."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None
        elif response.status_code >= 500:
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("🔧 Error del servidor del agente. Reintente en unos minutos."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None
        elif response.status_code >= 400:
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("❌ Error en la petición al agente. Verifique el formato del payload."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None

        try:
            return response.json()
        except ValueError:
            bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
            if bot_user:
                self.sudo().message_post(
                    body=_("⚠️ Respuesta inválida del agente. Se esperaba JSON."),
                    author_id=bot_user.partner_id.id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            return None

    def _get_conversation_history(self, channel_id):
        """Get recent messages from the channel for context."""
        messages = self.env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel_id),
            ('message_type', '=', 'comment'),
        ], order='create_date desc', limit=20)

        history = []
        bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        bot_partner_id = bot_user.partner_id.id if bot_user else None

        for msg in reversed(messages):
            if msg.author_id.id == bot_partner_id:
                role = 'assistant'
            else:
                role = 'user'
            history.append({
                'role': role,
                'content': msg.body,
            })
        return history

    def _post_bot_response(self, response_data):
        """Post the bot's response to the channel."""
        bot_user = self.env.ref('l10n_ve_compliance_manager.user_contafis_bot', raise_if_not_found=False)
        if not bot_user:
            return

        response = response_data.get('response', '')
        warnings = response_data.get('warnings', [])

        body = response
        if warnings:
            warning_text = '\n'.join([f'⚠️ {w}' for w in warnings])
            body += f'\n\n<blockquote>{warning_text}</blockquote>'

        self.sudo().message_post(
            body=body,
            author_id=bot_user.partner_id.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
