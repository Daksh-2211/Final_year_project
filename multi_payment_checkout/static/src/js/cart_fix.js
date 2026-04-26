/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {CartNotification} from "@website_sale/js/cart_notification";

patch(CartNotification.prototype, {
    showCartNotification(notification) {
        // Safety check - if lines undefined, skip notification
        if (!notification || !notification.lines) {
            console.warn("GTM: Cart notification missing lines, skipping.");
            return;
        }
        return super.showCartNotification(...arguments);
    }
});