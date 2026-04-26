/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CtaWidget = publicWidget.Widget.extend({
    selector: '.js_cta_widget',

    events: {
        'click .js_close_cta': '_onCloseClick',
    },

    _onCloseClick: function (ev) {
        ev.preventDefault();
        // Button hide karva mate
        this.$el.hide();
    },
});