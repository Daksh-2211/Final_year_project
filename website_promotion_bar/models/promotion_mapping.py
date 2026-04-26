# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import models, fields, api, _

from odoo.exceptions import UserError


class PromotionMapping(models.Model):
    _name = "promotion.mapping"
    _description = "Promotion Bars Mapping for Webpage"

    name = fields.Char('Name', compute="_compute_name", store=True, index=True)
    page_id = fields.Many2one("ir.ui.view", 'Page', required=True,
        help="Select Page on which you want to show promotion bar.")
    position = fields.Selection([
        ('top', 'Top'),
        ('right', 'Right'),
        ('bottom', 'Bottom'),
        ('left', 'Left'),
    ], string='Position', default='top', required=True, copy=False, help="At which position of page.")
    visibility = fields.Selection([('portal', 'Portal'), ('public', 'Public')],
                                  'Visibility', default='public',
                                  help="Type of user can see promotion bar.")
    date_start = fields.Date('Start Date', required=True,
                             help="Date from promotion bar would be visible.")
    date_end = fields.Date('End Date', help="Date at promotion bar expires.")
    content = fields.Html('Content', help="What content you want to show.")
    publish = fields.Boolean('Publish', help="Button for promotion showing or not?")
    view_id = fields.Many2one("ir.ui.view", 'View', copy=False)
    is_multi_promotion = fields.Boolean('Is Multi Promotion?',
        help="Check a promotion is Single Promotion or Successive Multi Promotion?")
    promotion_id = fields.Many2one("promotion.mapping", 'Main Promotion',
                                   help="To connect with Parent Div.")
    promotion_ids = fields.One2many("promotion.mapping", 'promotion_id', 'Multi Promotions',
                                    help="To connect with Successive Div.")

    @api.onchange('is_multi_promotion')
    def onchange_is_multi_promotion(self):
        if not self.is_multi_promotion:
            self.promotion_id = False

    @api.onchange('position')
    def onchange_position(self):
        self.is_multi_promotion = False
        self.promotion_id = False

    @api.depends('page_id', 'position')
    def _compute_name(self):
        for rec in self:
            if rec.page_id and rec.position and rec.id:
                rec.name = "{page_name} ({position}-{rec_id})".format(
                    page_name=rec.page_id.name,
                    position=dict(rec._fields['position'].selection).get(rec.position),
                    rec_id=rec.id)

    @api.depends('page_id', 'position')
    def _compute_display_name(self):
        for rec in self:
            if not rec.id:
                rec.display_name = "New"
            else:
                if rec.is_multi_promotion:
                    rec.display_name = "{page_name}-{position} (Secondary-Multi Promotion)".format(
                        page_name=rec.page_id.name,
                        position=dict(rec._fields['position'].selection).get(rec.position))
                else:
                    if rec.promotion_ids:
                        rec.display_name = "{page_name}-{position} (Main-Multi Promotion)".format(
                            page_name=rec.page_id.name,
                            position=dict(rec._fields['position'].selection).get(rec.position))
                    else:
                        rec.display_name = "{page_name}-{position} (Single Promotion)".format(
                            page_name=rec.page_id.name,
                            position=dict(rec._fields['position'].selection).get(rec.position))

    def get_arch(self, rec):
        today = "datetime.datetime.today().strftime('%Y-%m-%d')"
        condition = "not request.website.is_public_user()" if rec.visibility == 'portal' else 'True'
        condition += """ and '{date_start}' &lt;= {today}""".format(date_start=rec.date_start, today=today)
        if rec.date_end:
            condition += """ and '{date_end}' &gt;= {today}""".format(date_end=rec.date_end, today=today)

        bar = "top_bottom" if rec.position in ['top', 'bottom'] else "left_right"
        modal = """
            <t t-set="content" t-value="website.env['promotion.mapping'].sudo().browse({rec_id}).content"/>
            <div t-if="config_setting.get('allow_pop_up')" class="modal" id="promotion_modal_{rec_id}" style="background-color: transparent;">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-body" t-attf-style="background:#{{config_setting.get('background_color')}};">
                            <t t-out="content"/>
                        </div>
                    </div>
                </div>
            </div>""".format(rec_id=rec.id)

        if rec.content:
            a = rec.content
            mytext = "<br />".join(a.split("<br>"))
            content = """
            <div class="less_content">
                <a t-if="config_setting.get('allow_cross')" href="#/" class="fa fa-times close_promotion"/>
                <a href="#/" class="promotion_link" data-toggle="modal" data-target="#promotion_modal_{rec_id}">
            """.format(rec_id=rec.id) + mytext + """</a></div>
            """
        else:
            content = "<p><br/></p>"

        style_1 = """background:#{{config_setting.get('background_color')}};""".format()
        style_2 = """max-height:#{{config_setting.get('{bar}_height')}};width:#{{config_setting.get('{bar}_width')}};""".format(bar=bar)

        promotion_div = """
            <div t-att-data-id="{rec_id}" t-if="{condition}" class="{position} promotion" t-attf-style="{style}">
                {content}
            </div>""".format(
            rec_id=rec.id,
            condition=condition,
            position=rec.position,
            style=style_1 + style_2 if rec.position in ['left', 'right'] else style_1,
            content=content)

        expr = "//div[@id='wrap']" if rec.position == 'bottom' else "//div[@id='wrap']"
        location = 'before' if rec.position == 'top' else 'after'

        if rec.position in ['left', 'right']:
            arch = """
                <data>
                    <xpath expr="{expr}" position="{location}">
                        <t t-set="config_setting" t-value="website.get_promotion_config_settings_values()"/>
                        {modal}
                        {promotion_div}
                    </xpath>
                </data>""".format(expr=expr,
                                  location=location,
                                  modal=modal,
                                  promotion_div=promotion_div)
        elif rec.is_multi_promotion:
            arch = """
                <data>
                    <xpath expr="//div[@id='main_{position}']" position="inside">
                        {modal}
                        <div class="carousel-item">
                            {promotion_div}
                        </div>
                    </xpath>
                </data>""".format(position=rec.position,
                                  modal=modal,
                                  promotion_div=promotion_div)
        else:
            arch = """
                <data>
                    <xpath expr="{expr}" position="{location}">
                        <t t-set="config_setting" t-value="website.get_promotion_config_settings_values()"/>
                        <div class="carousel slide" data-ride="carousel" data-interval="5000" t-attf-style="{style}">
                            <div id="main_{position}" class="carousel-inner">
                                {modal}
                                <div class="carousel-item active">
                                    {promotion_div}
                                </div>
                            </div>
                        </div>
                    </xpath>
                </data>""".format(expr=expr,
                                  location=location,
                                  style=style_2,
                                  position=rec.position,
                                  modal=modal,
                                  promotion_div=promotion_div)

        return arch

    def write(self, vals):
        res = super(PromotionMapping, self).write(vals)
        for rec in self:
            view_data = {}
            if vals.get('page_id') or vals.get('position') or \
                vals.get('is_multi_promotion', 'no value') != 'no value' or vals.get('promotion_id'):
                rec.publish = False
                view_data.update({'active': False})
            if vals.get('is_multi_promotion', 'no value') == True or vals.get('position'):
                if rec.promotion_ids:
                    for obj in rec.promotion_ids:
                        obj.write({
                            'is_multi_promotion': False,
                            'promotion_id': False,
                            'publish': False,
                        })
            if vals.get('is_multi_promotion', 'no value') == True or vals.get('promotion_id'):
                view_data.update({
                    'name': 'Inherited Promotion ' + rec.page_id.name,
                    'inherit_id': rec.promotion_id.view_id.id,
                })
            if vals.get('page_id') or vals.get('is_multi_promotion', 'no value') == False:
                view_data.update({
                    'name': 'Promotion ' + rec.page_id.name,
                    'inherit_id': rec.page_id.id,
                })
            if vals.get('position') or vals.get('content') or vals.get('visibility') \
                or vals.get('date_start') or vals.get('date_end', 'no value') != 'no value' \
                or vals.get('is_multi_promotion', 'no value') != 'no value':
                view_data.update({'arch': self.get_arch(rec)})
            view_obj = rec.view_id.write(view_data)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PromotionMapping, self).create(vals_list)
        view_data = {
            'name': 'Promotion ' + res.page_id.name,
            'type': 'qweb',
            'priority': 16,
            'active': res.publish,
            'inherit_id': res.page_id.id,
            'mode': 'extension',
            'arch': self.get_arch(res),
        }
        if res.is_multi_promotion:
            view_data.update({
                'name': 'Inherited Promotion ' + res.page_id.name,
                'inherit_id': res.promotion_id.view_id.id,
            })
        res.view_id = self.env["ir.ui.view"].create(view_data)
        return res

    def unlink(self):
        for rec in self:
            if rec.promotion_ids:
                rec.promotion_ids.write({
                    'is_multi_promotion': False,
                    'promotion_id': False,
                    'publish': False,
                })
                rec.promotion_ids.mapped('view_id').write({'active': False})
            rec.view_id.unlink()
        return super(PromotionMapping, self).unlink()

    @api.model
    def create_wizard(self):
        wizard_id = self.env["website.message.wizard"].create({
            'message':
            _("Currently a Website Promotion Bar at the same position for this page is active." \
              " You can not active other Website Promotion Bar. If you want Multi Promotion Bar," \
              " You can Allow this for only Top and Bottom position. Otherwise you need to" \
              " deactive the previous active Promotion Bar and active new Promotion Bar" \
              " then click on 'Deactive Previous And Active New' button else click on 'cancel'."
              )
        })
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

    def promotion_publish_button(self):
        self.ensure_one()
        if self.publish:
            if not self.is_multi_promotion:
                active_ids = self.env["promotion.mapping"].search([
                    ('publish', '=', True), ('id', 'not in', [self.id]),
                    ('page_id', '=', self.page_id.id),
                    ('position', '=', self.position)
                ])
                for active_id in active_ids:
                    active_id.publish = not active_id.publish
                    active_id.view_id.active = not active_id.view_id.active
            self.publish = not self.publish
            self.view_id.active = not self.view_id.active
        else:
            if self.is_multi_promotion:
                if self.promotion_id.publish:
                    self.publish = not self.publish
                    self.view_id.active = not self.view_id.active
                else:
                    raise UserError(
                        _("Firstly You need to Publish its Parent Promotion Bar (%s)." \
                          " Or Make it Single/Main-Multi Promotion Bar.") % (self.promotion_id.name))
            else:
                active_ids = self.env["promotion.mapping"].search([
                    ('publish', '=', True), ('id', 'not in', [self.id]),
                    ('page_id', '=', self.page_id.id),
                    ('position', '=', self.position)
                ])
                if active_ids:
                    return self.create_wizard()
                self.publish = not self.publish
                self.view_id.active = not self.view_id.active
