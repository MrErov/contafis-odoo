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
    l10n_ve_digitize_url = fields.Char(
        string="URL del servicio de digitalización",
        config_parameter='l10n_ve_digitize.url',
        help="URL del endpoint /digitize del servicio contafis-assistant. Ej: https://tu-servicio/digitize",
    )
    l10n_ve_digitize_timeout_seconds = fields.Integer(
        string="Timeout de digitalización (segundos)",
        config_parameter='l10n_ve_digitize.timeout_seconds',
        default=30,
        help="Tiempo máximo de espera de la respuesta del servicio de digitalización.",
    )
    l10n_ve_digitize_max_image_mb = fields.Float(
        string="Tamaño máximo de imagen (MB)",
        config_parameter='l10n_ve_digitize.max_image_mb',
        default=5.0,
        help="Límite local de la imagen antes de enviarla al servicio de digitalización.",
    )
