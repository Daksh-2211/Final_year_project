from odoo import models, fields, api, _
from odoo.fields import Date
import re


class PromotionMapping(models.Model):
    _inherit = "promotion.mapping"

    menu_id = fields.Many2one(
        "website.menu",
        string="Website Menu",
        help="Select menu; bar will appear on it, all sub-menus, mega-menu links, and events."
    )

    page_id = fields.Many2one(
        "ir.ui.view",
        string="Page",
        required=False
    )

    def _get_all_menu_urls(self, menu):
        """Recursively collect all URLs from a menu and its children, including event paths."""
        urls = set()
        if menu.url:
            urls.add(menu.url.strip())

        # 1. Collect from Child Menu records
        for child in menu.child_id:
            urls.update(self._get_all_menu_urls(child))

        # 2. Collect from Mega Menu content (your custom HTML links)
        if menu.is_mega_menu and menu.mega_menu_content:
            mega_links = re.findall(r'href=["\'](/?[\w\-/]+)["\']', menu.mega_menu_content)
            for link in mega_links:
                clean_link = link.strip()
                if clean_link and not clean_link.startswith(('http', 'mailto', '#')):
                    urls.add(clean_link)

        return urls

    def _menu_visibility_condition(self, rec):
        """Build a condition string for parent, children, mega-menu links, and event registration pages."""
        today = Date.context_today(self)
        if rec.date_start and today < fields.Date.from_string(rec.date_start):
            return "False"
        if rec.date_end and today > fields.Date.from_string(rec.date_end):
            return "False"

        # 2. Base Condition
        condition = "request"

        # 3. URL Logic
        if rec.menu_id:
            all_urls = self._get_all_menu_urls(rec.menu_id)
            is_home = any(u in ['/', ''] for u in all_urls)
            url_list = list(all_urls)

            special_path_logic = "request.httprequest.path.startswith('/event')"
            if '/laserarena-camp' not in url_list:
                special_path_logic += " or request.httprequest.path.startswith('/laserarena-camp')"

            if is_home:
                condition = f"request and (request.httprequest.path in ['/', '/index', '', '/sk', '/sk/'] or {special_path_logic} or any(request.httprequest.path == u or request.httprequest.path.startswith(u + '/') for u in {url_list}))"
            else:
                condition = f"request and ({special_path_logic} or any(request.httprequest.path == u or request.httprequest.path.startswith(u + '/') for u in {url_list}))"

        return condition

    def get_arch(self, rec):
        condition = self._menu_visibility_condition(rec)
        bg_color = "config_setting.get('background_color', 'D0442C')"

        return f"""
            <data>
                <xpath expr="//main" position="before">
                    <t t-set="config_setting" t-value="website.get_promotion_config_settings_values() or {{}}"/>

                    <div t-if="{condition}"
                         class="promotion_bar_final"
                         t-att-style="'background:#' + str({bg_color}) + '; width:100%; display:block !important; z-index:998; position:relative; min-height:30px; margin-bottom: 0px;'">

                        <div class="container-fluid d-flex align-items-center justify-content-center" 
                             style="padding: 4px 0; min-height: 30px;">

                            <div class="text-center w-100" style="color: white !important; line-height: 1.2; display: flex; align-items: center; margin-top:10px; margin-bottom:10px; justify-content: center;">
                                <a href="#/" class="promotion_link" 
                                   data-bs-toggle="modal" 
                                   t-att-data-bs-target="'#promotion_modal_{rec.id}'"
                                   style="color: white !important; font-weight: bold; text-decoration: none !important; font-size: 14px; margin: 0;">
                                    <t t-out="website.env['promotion.mapping'].sudo().browse({rec.id}).content"/>
                                </a>

                                <a t-if="config_setting.get('allow_cross')" 
                                   href="#/" 
                                   class="fa fa-times close_promotion ms-3" 
                                   style="color: white !important; cursor: pointer; text-decoration: none; font-size: 12px; opacity: 0.8;"/>
                            </div>
                        </div>
                    </div>

                    <div class="modal fade" t-att-id="'promotion_modal_{rec.id}'" tabindex="-1" aria-hidden="true" style="z-index: 1000000;">
                        <div class="modal-dialog modal-dialog-centered">
                            <div class="modal-content">
                                <div class="modal-body p-5 text-center" t-att-style="'background:#' + str({bg_color}) + '; color: white;'">
                                    <t t-out="website.env['promotion.mapping'].sudo().browse({rec.id}).content"/>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" style="position: absolute; top: 15px; right: 15px;"></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </xpath>
            </data>
        """

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.view_id:
                rec.view_id.write({'arch': rec.get_arch(rec), 'active': rec.publish})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        layout_view = self.env.ref('website.layout')
        for vals in vals_list:
            if not vals.get('page_id'):
                vals['page_id'] = layout_view.id
        return super().create(vals_list)

    def promotion_publish_button(self):
        self.ensure_one()
        self.publish = not self.publish
        if self.view_id:
            self.view_id.active = self.publish
        return True