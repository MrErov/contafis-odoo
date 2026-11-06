/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Point the realtime bus to the evented (gevent) port.
 *
 * Odoo builds the websocket URL from ``window.origin``. With multi-worker
 * mode the websocket handshake must reach the evented port, not the regular
 * HTTP worker. ``session.contafis_bus_port`` is emitted by the backend from
 * Odoo's ``gevent_port`` (see models/ir_http.py).
 *
 * The rewrite only happens when the page is served through an explicit,
 * non-standard port. Deployments behind a reverse proxy on 80/443 keep the
 * same origin and are left untouched.
 */
function busServerURL() {
    const origin = new URL(window.origin);
    const busPort = session.contafis_bus_port;
    if (busPort && origin.port && origin.port !== String(busPort)) {
        origin.port = String(busPort);
    }
    return origin.origin;
}

registry.category("services").add(
    "bus.parameters",
    {
        start() {
            return { serverURL: busServerURL() };
        },
    },
    { force: true }
);
