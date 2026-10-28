from odoo import fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    api_token = fields.Char(
        string='Token API Asistente Fiscal',
        groups='base.group_system',
        help='Token Bearer para autenticar peticiones al backend FastAPI del '
             'Asistente Fiscal (http://localhost:8000/chat). Solo visible y '
             'editable por administradores (base.group_system).',
    )

    def write(self, vals):
        if 'api_token' in vals and not self.env.user.has_group('base.group_system'):
            raise AccessError('Solo los administradores pueden modificar el token API.')
        return super().write(vals)
