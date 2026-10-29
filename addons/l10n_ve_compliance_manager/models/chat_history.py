from odoo import fields, models


class ChatHistory(models.Model):
    _name = 'l10n.ve.chat.history'
    _description = 'Historial de Chat Asistente Fiscal'
    _order = 'create_date ASC'
    _rec_name = 'conversation_id'

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    conversation_id = fields.Char(
        string='ID Conversación',
        required=True,
        index=True,
        help='UUID de la conversación (v4). Agrupa mensajes relacionados.',
    )
    role = fields.Selection([
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
    ], string='Rol', required=True)
    content = fields.Text(string='Contenido', required=True)
    warnings = fields.Json(
        string='Warnings',
        default=list,
        help='Array de strings con advertencias del asistente (ej. scope_admin_key).',
    )
    create_date = fields.Datetime(string='Fecha creación', readonly=True)
    create_uid = fields.Many2one(
        'res.users',
        string='Creado por',
        readonly=True,
    )

    _unique_msg_per_conv_per_user_per_company = models.Constraint(
        'UNIQUE(user_id, company_id, conversation_id, create_date)',
        'Ya existe un mensaje con los mismos datos en esta conversación.',
    )
