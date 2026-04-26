# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import models, fields, api


class WebkulWebsiteAddons(models.TransientModel):
    _inherit = 'res.config.settings'

    def get_promotion_configuration_view(self):
        promotion_config_ids = self.env["promotion.config.settings"].search([])
        imd = self.env['ir.model.data']
        action = self.env["ir.actions.actions"]._for_xml_id(
            "website_promotion_bar.website_promotion_config_settings_action")
        list_view_id = imd._xmlid_to_res_id('website_promotion_bar.view_promotion_config_settings_tree')
        form_view_id = imd._xmlid_to_res_id('website_promotion_bar.view_promotion_config_settings_form')
        if len(promotion_config_ids) == 1:
            action.update({
                'views': [(form_view_id, 'form')],
                'res_id': promotion_config_ids[0].id,
            })
        else:
            action.update(views=[[list_view_id, 'tree'], [form_view_id, 'form']])
        return action
