from odoo import models
from odoo.tools import config


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose the evented (websocket) port to the web client.

        Odoo's bus service derives the websocket URL from ``window.origin``.
        When Odoo runs with ``workers > 0`` behind a port mapping that only
        publishes the HTTP port (for example ``8090 -> 8069``), the browser
        opens the websocket against the regular HTTP worker. That worker is
        not evented, so the handshake fails with::

            Couldn't bind the websocket. Is the connection opened on the
            evented port (8072)?

        and the web client shows "Se perdió la conexión en tiempo real".

        Emitting the configured ``gevent_port`` lets the frontend target the
        evented port, which docker-compose already publishes.
        """
        info = super().session_info()
        info["contafis_bus_port"] = str(config.get("gevent_port") or "")
        return info
