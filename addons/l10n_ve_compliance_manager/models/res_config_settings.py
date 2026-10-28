from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ve_chat_webhook_url = fields.Char(
        string="Webhook URL",
        config_parameter='l10n_ve_chat.webhook_url',
        help="URL del endpoint que recibirá los mensajes (POST JSON). Ej: https://tu-n8n.com/webhook/contafis",
    )
    l10n_ve_chat_auth_token = fields.Char(
        string="Auth Token",
        config_parameter='l10n_ve_chat.auth_token',
        help="Token Bearer que se enviará en el header Authorization. Deje vacío si no se requiere autenticación.",
    )
