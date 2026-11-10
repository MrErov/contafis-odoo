/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Expose the gevent port for websocket connections.
 *
 * The bus.parameters service should return the HTTP origin (for worker bundle).
 * The websocket connection is patched globally in bus_websocket_port.js to use the gevent port.
 *
 * We store the gevent port in session.contafis_bus_port (set by ir_http.py).
 */
registry.category("services").add(
    "bus.parameters",
    {
        start() {
            // Return the HTTP origin (for worker bundle loading)
            // The websocket connection is patched globally in bus_websocket_port.js
            return { serverURL: window.origin };
        },
    },
    { force: true }
);
