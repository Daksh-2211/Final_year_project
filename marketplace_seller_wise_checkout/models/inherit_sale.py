# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# License URL : https://store.webkul.com/license.html/
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################

from odoo import api, models, fields, _
from odoo.addons.website.models import ir_http
import logging
import random
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    marketplace_seller_id = fields.Many2one("res.partner", string="Seller", domain="[('seller','=',True)]", default=lambda self: self.env.user.partner_id.id if self.env.user.partner_id and self.env.user.partner_id.seller else self.env['res.partner'],)
    mp_order_state = fields.Selection([
        ("new","New"),
        ("pending","Pending"),
        ("approved","Approved") ,
        ("shipped","Shipped"),
        ("done","Done"),
        ("cancel","Cancelled"),
        ], default="new", copy=False, tracking=True)
    show_shipped_button = fields.Boolean("Show shipped button",compute="_show_shipped_button")

    def _unfollow_customer(self):
        customer = self.env['mail.followers'].search([('res_id','=',self.id),('res_model','=','sale.order'),('partner_id','=',self.partner_id.id)])
        if customer:
            customer.unlink()

    def _adding_followers(self):
        partner_id = self.env.user.partner_id
        if not self.env['mail.followers'].search([('res_id','=',self.id),('res_model','=','sale.order'),('partner_id','=',partner_id.id)]):
            follower_id = self.env['mail.followers'].sudo().create({
        'res_id':self.id,
        'res_model':'sale.order',
        'partner_id':partner_id.id

            })

    def _show_shipped_button(self):
        check_order_line_type=self.order_line.filtered(lambda l : l.product_type != "service")
        if check_order_line_type:
            self.show_shipped_button = True
        else:
            self.show_shipped_button = False


    def button_done_order(self):
        for rec in self:
            if rec.marketplace_seller_id:
                rec.sudo().write({'mp_order_state':'done'})
                if rec.order_line:
                    for line in rec.order_line:
                        line.sudo().marketplace_state = "done"
                rec._adding_followers()

    def button_seller_approve_order(self):
        for rec in self:
            if rec.marketplace_seller_id:
                rec.sudo().write({'mp_order_state':'approved'})
                if rec.order_line:
                    for line in rec.order_line:
                        line.sudo().marketplace_state = "approved"
                rec._adding_followers()
    def button_seller_confirm_order(self):
        for rec in self:
            if rec.marketplace_seller_id:
                rec.sudo().action_confirm()
                rec.sudo().write({'mp_order_state':'pending'})
                if rec.order_line:
                    for line in rec.order_line:
                        line.sudo().marketplace_state = "pending"
                rec._unfollow_customer()
                rec._adding_followers()

    def button_seller_cancel_order(self):
        for rec in self:
            if rec.marketplace_seller_id:
                rec.sudo().action_cancel()
                rec.sudo().write({'mp_order_state':'cancel'})
                if rec.order_line:
                    for line in rec.order_line:
                        line.sudo().button_cancel()
                rec._adding_followers()

    def action_cancel(self):
        res = super(SaleOrder,self).action_cancel()
        for rec in self:
            if rec.marketplace_seller_id:
                rec.write({'mp_order_state':'cancel'})
            rec._adding_followers()
        return res

    def action_draft(self):
        result = super(SaleOrder,self).action_draft()
        for rec in self:
            if rec.marketplace_seller_id:
                rec.write({'mp_order_state':'new'})
        return result

    def action_view_delivery(self):
        res = super(SaleOrder, self).action_view_delivery()
        if self._context.get('mp_order'):
            action = self.env.ref('odoo_marketplace.marketplace_stock_picking_action').sudo().read()[0]
            pickings = self.mapped('picking_ids')
            if len(pickings) > 1:
                action['domain'] = [('id', 'in', pickings.ids)]
            elif pickings:
                action['views'] = [(self.env.ref('odoo_marketplace.marketplace_picking_stock_modified_form_view').id, 'form')]
                action['res_id'] = pickings.id
            return action
        return res

    def action_confirm(self):
        result = super(SaleOrder, self).action_confirm()
        for rec in self:
            if rec.marketplace_seller_id:
                rec.write({'mp_order_state':'pending'})
        return result

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def write(self, values):
        result = super(SaleOrderLine, self).write(values)
        for rec in self:
            order = rec.order_id
            order_line = order.order_line.filtered(lambda l : l.product_type != "service")
            if order and all([ol.marketplace_state == 'shipped' for ol in order.order_line]):
                order.write({'mp_order_state': 'shipped'})
        return result

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _compute_cart_qty(self):
        website = ir_http.get_request_website()
        if not website:
            self.cart_qty = 0
            return
        for product in self:
            seller_id = product.marketplace_seller_id.id if product.marketplace_seller_id else None
            cart = website.sale_get_order(seller_id=seller_id)
            product.cart_qty = sum(cart.order_line.filtered(lambda p: p.product_id.id == product.id).mapped('product_uom_qty')) if cart else 0
