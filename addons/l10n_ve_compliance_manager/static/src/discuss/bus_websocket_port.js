/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Patch global WebSocket to fix bus websocket port.
 *
 * The bus worker bundle loads from HTTP origin (port 8069) via bus.parameters.serverURL.
 * The websocket connection must use gevent port (8072) from session.contafis_bus_port.
 *
 * This patches the global WebSocket constructor to rewrite the bus websocket URL.
 */
registry.category("main").add("l10n_ve_websocket_port_patch", {
    start() {
        const originalWebSocket = window.WebSocket;
        const geventPort = session.contafis_bus_port;

        if (!geventPort) {
            return; // No gevent port configured, use default
        }

        window.WebSocket = function(url, protocols) {
            // Fix bus websocket port: rewrite localhost:8069 to localhost:8072 for bus websocket connections
            if (typeof url === 'string' && url.includes('/websocket') && url.includes('localhost:8069')) {
                url = url.replace('localhost:8069', `localhost:${geventPort}`);
            }
            return new originalWebSocket(url, ...arguments.slice(1));
        };
        window.WebSocket.prototype = originalWebSocket.prototype;
    },
}, { force: true });
