# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import api, fields, models


class WebsiteMessageWizard(models.TransientModel):
    _inherit = "website.message.wizard"

    def update_latest_record(self):
        active_model = self.env[self._context.get('active_model')]
        if active_model == self.env["promotion.mapping"]:
            active_id = self._context.get('active_id') or self._context.get('active_ids')[0]
            active_record = active_model.browse(active_id)
            is_active_records = active_model.search([
                ('publish', '=', True),
                ('page_id', '=', active_record.page_id.id),
                ('position', '=', active_record.position)
            ])
            for is_active_record in is_active_records:
                is_active_record.publish = not is_active_record.publish
                is_active_record.view_id.active = not is_active_record.view_id.active
            active_record.publish = not active_record.publish
            active_record.view_id.active = not active_record.view_id.active
            return True
        else:
            return super(WebsiteMessageWizard, self).update_latest_record()

    def cancel(self):
        active_model = self.env[self._context.get('active_model')]
        active_id = self._context.get('active_id') or self._context.get('active_ids')[0]
        active_record = active_model.browse(active_id)
        if active_model == self.env["promotion.mapping"]:
            return True
        else:
            return super(WebsiteMessageWizard, self).cancel()
