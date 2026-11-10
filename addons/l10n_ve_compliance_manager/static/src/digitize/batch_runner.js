/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * Batch runner (spec 007-C).
 *
 * The server-side batch loop keeps one HTTP request open for the whole
 * batch, which exceeds Odoo's ``limit_time_real`` with 3+ receipts. This
 * widget drives the batch from the client instead: one RPC per receipt
 * (~60 s each) and a record reload after every line, so the accountant
 * sees each row move from "Pendiente" to "Analizado"/"Error".
 *
 * The state lives outside the component so it survives the record reloads
 * that happen between lines (the field component can be recreated). OWL
 * does not always re-render this module-level state on its own, so every
 * mutation calls ``refreshRunner()`` on the latest mounted instance.
 */
const batchState = {
    running: false,
    current: 0,
    total: 0,
};

let activeRunner = null;

function refreshRunner() {
    if (!activeRunner) {
        return;
    }
    try {
        activeRunner.render();
    } catch {
        // The form may have replaced the component during a record reload.
    }
}

export class BatchRunner extends Component {
    static template = "l10n_ve_compliance_manager.BatchRunner";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = batchState;
        activeRunner = this;
    }

    willUnmount() {
        if (activeRunner === this) {
            activeRunner = null;
        }
    }

    get buttonLabel() {
        if (!this.state.running) {
            return _t("Analizar lote");
        }
        const current = Math.min(this.state.current + 1, this.state.total);
        return _t("Analizando %(current)s de %(total)s\u2026", {
            current,
            total: this.state.total,
        });
    }

    /**
     * Reload the wizard without letting the runner freeze.
     *
     * ``record.load()`` sometimes never settles when the form is refreshed
     * right after the last x2many row changes (the HTTP request completes but
     * the model promise stays pending). The runner must keep going: the next
     * receipt has to be processed and the button has to be released.
     */
    async _reloadRecord() {
        await Promise.race([
            this.props.record.load(),
            new Promise((resolve) => setTimeout(resolve, 8000)),
        ]).catch(() => {});
    }

    async onClick() {
        if (this.state.running) {
            return;
        }
        const record = this.props.record;
        const saved = await record.save();
        if (!saved) {
            return;
        }
        const wizardId = record.resId;
        const lines = await this.orm.call(
            "l10n.ve.digitize.wizard",
            "get_batch_line_ids",
            [[wizardId]]
        );
        const pending = lines.filter((line) => line.status !== "done");
        if (!pending.length) {
            this.notification.add(
                lines.length
                    ? _t(
                          "Todas las filas ya est\u00e1n analizadas. " +
                              "Elimine una fila y agr\u00e9guela de nuevo para reanalizarla."
                      )
                    : _t("Agregue al menos un recibo al lote antes de analizar."),
                { type: "info" }
            );
            return;
        }

        this.state.running = true;
        this.state.current = 0;
        this.state.total = pending.length;
        refreshRunner();
        let ok = 0;
        let failed = 0;
        try {
            for (const line of pending) {
                const result = await this.orm.call(
                    "l10n.ve.digitize.wizard",
                    "action_digitize_line",
                    [[wizardId], line.id]
                );
                if (result.status === "error") {
                    failed += 1;
                } else {
                    ok += 1;
                }
                this.state.current += 1;
                refreshRunner();
                await this._reloadRecord();
            }
            this.notification.add(
                failed
                    ? _t(
                          "Lote finalizado: %(ok)s analizados y %(failed)s con error.",
                          { ok, failed }
                      )
                    : _t("Lote finalizado: %(ok)s recibos analizados.", { ok }),
                { type: failed ? "warning" : "success" }
            );
        } catch (error) {
            this.notification.add(
                error?.data?.message ||
                    error?.message ||
                    _t("No se pudo analizar el lote."),
                { type: "danger" }
            );
            await this._reloadRecord();
            return;
        } finally {
            this.state.running = false;
            refreshRunner();
        }
    }
}

export const batchRunnerField = {
    component: BatchRunner,
    supportedTypes: ["boolean"],
    displayName: _t("Batch Runner"),
    extractProps: () => ({}),
};

registry.category("fields").add("l10n_ve_batch_runner", batchRunnerField);
