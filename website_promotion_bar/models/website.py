# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import models, fields, api


class Website(models.Model):
    _inherit = "website"

    @api.model
    def get_promotion_config_settings_values(self):
        """ this function retrn all configuration value for website promotion module."""
        res = {}
        promotion_config_values = self.env["promotion.config.settings"].sudo(
        ).search([('is_active', '=', True)], limit=1)
        if promotion_config_values:
            res = {
                'background_color': promotion_config_values.background_color,
                'top_bottom_height': promotion_config_values.top_bottom_height,
                'top_bottom_width': promotion_config_values.top_bottom_width,
                'left_right_height': promotion_config_values.left_right_height,
                'left_right_width': promotion_config_values.left_right_width,
                'allow_cross': promotion_config_values.allow_cross,
                'allow_pop_up': promotion_config_values.allow_pop_up,
            }
        return res
