# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PromotionConfigSettings(models.Model):
    _name = "promotion.config.settings"
    _description = "Configuration settings for Promotion bars"

    name = fields.Char(string='Name')
    is_active = fields.Boolean(
        string="Active on website",
        help="Only single configuration will be active at a time.")
    background_color = fields.Char(string='Background Color',size=7,
                                   help="Enter Hexa Decimal Value of Color", default="#FFFFFF")
    top_bottom_height = fields.Char(string='Top/Bottom Height', help="Only for Top and Bottom Promotion Bar.")
    top_bottom_width = fields.Char(string='Top/Bottom Width', help="Only for Top and Bottom Promotion Bar.")
    left_right_height = fields.Char(string='Left/Right Height', help="Only for Left and Right Promotion Bar")
    left_right_width = fields.Char(string='Left/Right Width', help="Only for Left and Right Promotion Bar")
    allow_cross = fields.Boolean(string='Cross Enable', help="Allow Cross button on Promotion Bar.")
    allow_pop_up = fields.Boolean(string='Pop Up Enable', help="Allow Pop Up of Promotion Bar.")

    @api.model
    def create_wizard(self):
        wizard_id = self.env["website.message.wizard"].create({'message': _(
            "Currently a Configuration Setting for Website Promotion Bar of this page is active." \
            " You can not active other Configuration Setting. So, If you want to deactive the" \
            " previous active configuration setting and active new configuration then click on" \
            " 'Deactive Previous And Active New' button else click on 'cancel'.")})
        return {
            'name': _("Message"),
            'view_mode': 'form',
            'view_id': False,
            'res_model': 'website.message.wizard',
            'res_id': wizard_id.id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new'
        }

    def toggle_is_active(self):
        active_ids = self.search([('is_active', '=', True),
                                  ('id', 'not in', [self.id])])
        for record in self:
            if active_ids:
                return self.create_wizard()
            record.is_active = not record.is_active

    def write(self, vals):
        res = super(PromotionConfigSettings, self).write(vals)
        active_ids = self.search([('is_active', '=', True)])
        if len(active_ids) > 1:
            raise ValidationError("You can not active more than one Configuration Settings.")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        active_ids = self.search([('is_active', '=', True)])
        if len(active_ids) and vals_list.get('is_active'):
            vals_list['is_active'] = False
        res = super(PromotionConfigSettings, self).create(vals_list)
        return res
