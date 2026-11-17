"""Cierre de los hallazgos P0-03 y P0-05 en bases ya instaladas.

``data/res_users_data.xml`` usa ``noupdate="1"``: quitar la contraseña del
XML no borra el hash que ya está almacenado en ``res_users``. Esta migración
elimina esa credencial y desactiva el usuario demo que se creó a mano en la
base de producción (no existe en los datos del módulo).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BOT_XMLID = 'l10n_ve_compliance_manager.user_contafis_bot'
LEGACY_DEMO_LOGIN = 'demo@contafis.local'


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    bot = env.ref(BOT_XMLID, raise_if_not_found=False)
    if bot:
        cr.execute('SELECT password FROM res_users WHERE id = %s', (bot.id,))
        row = cr.fetchone()
        if row and row[0]:
            cr.execute('UPDATE res_users SET password = NULL WHERE id = %s', (bot.id,))
            _logger.warning('P0-03: contraseña del bot %s eliminada.', bot.login)

    demo = env['res.users'].with_context(active_test=False).search(
        [('login', '=', LEGACY_DEMO_LOGIN)], limit=1,
    )
    if demo and demo.active:
        demo.write({'active': False})
        _logger.warning('P0-05: usuario demo %s desactivado.', LEGACY_DEMO_LOGIN)
