/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Thread } from "@mail/core/common/thread";

/**
 * Guard the "new messages" banner against a desynchronised separator.
 *
 * Upstream ``Thread.onClickUnreadMessagesBanner`` calls
 * ``messageHighlight.highlightMessage(thread.firstUnreadMessage, thread)``
 * without checking the message first. ``firstUnreadMessage`` is a computed
 * field that can be ``null`` when the member's ``new_message_separator_ui``
 * no longer maps to a loaded message, which makes the client crash with:
 *
 *     TypeError: Cannot read properties of undefined (reading 'notIn')
 *
 * The banner still scrolls to the separator, but only highlights a message
 * when there is one.
 */
patch(Thread.prototype, {
    async onClickUnreadMessagesBanner() {
        const thread = this.props.thread;
        const separator = thread?.self_member_id?.new_message_separator_ui;
        if (separator) {
            await thread.loadAround(separator);
        }
        if (thread?.firstUnreadMessage) {
            this.messageHighlight?.highlightMessage(
                thread.firstUnreadMessage,
                thread
            );
        }
    },
});
