/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("actions").add("pohoda_download", async (env, action) => {
    window.open(action.params.url, "_blank");
    env.services.action.doAction({ type: "ir.actions.act_window_close" });
});
