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
from odoo import models, fields, api, _
from odoo.addons.website_sale_stock.models.sale_order import SaleOrder as WebsiteSaleStock
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    admin_commission = fields.Float(string="Admin commission",compute="_compute_admin_commission",default='0.0')
    seller_amount = fields.Float(string="Seller amount",compute="_compute_seller_amount",default='0.0')

    def _compute_admin_commission(self):
        """Compute admin commission"""
        admin_commission = 0
        for line in self.order_line:
            if line.admin_commission:
                admin_commission = admin_commission+line.admin_commission
        self.admin_commission = admin_commission

    def _compute_seller_amount(self):
        """Compute seller amount"""
        seller_amount = 0
        for line in self.order_line:
            if line.seller_amount:
                seller_amount = seller_amount+line.seller_amount
        self.seller_amount = seller_amount

    def action_cancel(self):
        result = super(SaleOrder,self).action_cancel()
        return result

    def action_so_done(self):
        """Mark Marketplace state to done"""
        for rec in self:
            if rec.order_line:
                mp_order_line = rec.order_line.filtered(lambda line: line.marketplace_seller_id != False and line.marketplace_state == "shipped" or line.marketplace_state == "approved" and line.product_type=="service")
                if mp_order_line:
                    mp_order_line.write({'marketplace_state':'done'})
                    mp_order_line._adding_followers()

    def action_draft(self):
        """ Mark Marketplace state to draft"""
        result = super(SaleOrder,self).action_draft()
        for rec in self:
            if rec.state == 'draft' and rec.order_line:
                mp_order_line = rec.order_line.filtered(lambda line: line.marketplace_seller_id != False)
                if mp_order_line:
                    mp_order_line.write({'marketplace_state':'new'})
        return result

    def get_seller_product_list(self, seller):
        """ Get seller products list"""
        self.ensure_one()
        product_list = []
        if seller:
            product_list = self.order_line.mapped('product_id').filtered(lambda l: l.marketplace_seller_id.id == seller.id).mapped('name')
        return ', '.join(product_list)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        """ Mark Marketplace state to Pending """
        for rec in self:
            if rec.order_line:
                mp_order_line = rec.order_line.filtered(lambda line: line.marketplace_seller_id != False)
                if mp_order_line:
                    mp_order_line.write({'marketplace_state':'pending'})
                    mp_order_line._adding_followers()
        resConfig = self.env['res.config.settings']
        if resConfig.get_mp_global_field_value("enable_notify_seller_on_new_order"):
            temp_id = resConfig.get_mp_global_field_value("notify_seller_on_new_order_m_tmpl_id")
            if temp_id:
                template_obj = self.env['mail.template'].browse(temp_id)
                for order in self:
                    seller_objs = order.order_line.mapped('marketplace_seller_id')
                    for seller in seller_objs:
                        template_obj.with_context(seller=seller).with_company(self.env.company).send_mail(order.id, True)
        return res


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line','mail.thread']

    STATES = [("new","New"),("pending","Pending"), ("approved","Approved") ,("shipped","Shipped"),("done","Done"),("cancel","Cancelled")]

    def name_get(self):
        """ Add record id to record.order_id name"""
        result = []
        for record in self:
            result.append((record.id, record.order_id.name))
        return result

    marketplace_seller_id = fields.Many2one(
        related='product_id.marketplace_seller_id', string='Marketplace Seller', store=True, copy=False)
    marketplace_state = fields.Selection(STATES, default="new", copy=False,tracking=True)
    mp_delivery_count = fields.Integer(string='Delivery Orders', compute='_compute_seller_picking_ids')

    order_carrier_id = fields.Many2one("delivery.carrier", related="order_id.carrier_id", string="Delivery Method")
    create_year = fields.Integer("Create Year",compute='_compute_create_year',store=True)
    seller_amount = fields.Float("Seller Amount", readonly=True)
    admin_commission = fields.Float("Admin Commission", readonly=True)
    pro_image1920 = fields.Image("image",related="product_id.image_1920")

    @api.model_create_multi
    def create(self,vals):
        res = super(SaleOrderLine, self.with_context(mail_create_nosubscribe=True)).create(vals)
        return res

    def get_mark_done_approval_wizard_action(self):
        """ Open bulk approval wizard """
        record = self.env["bulk.action.details"].create({
            'sale_order_line_ids': self.ids
        })
        return {
            'name':_('Mark Done'),
            'type':'ir.actions.act_window',
            'res_model':'bulk.action.details',
            'view_mode':'form',
            'res_id' : record.id,
            'target':'new',
        }
    
    def get_mass_confirm_wizard_action(self):
        """ Server Action to confirm selected records """

        record = self.env["mass.confirm.details"].create({
            'sale_order_line_ids': self.ids
        })
        return {
            'name':_('Mass Confirm'),
            'type':'ir.actions.act_window',
            'res_model':'mass.confirm.details',
            'view_mode':'form',
            'res_id' : record.id,
            'target':'new',
        }

    def get_approved_wizard_action(self):
        """ Server Action to Approve selected records """

        record = self.env["mass.action.details"].create({
            'sale_order_line_ids': self.ids
        })
        return {
            'name':_('Mass Approved'),
            'type':'ir.actions.act_window',
            'res_model':'mass.action.details',
            'view_mode':'form',
            'res_id' : record.id,
            'target':'new',
        }

    def _adding_followers(self):
        """Add user in follower list"""
        partner_id = self.env.user.partner_id
        for rec in self:
            if not self.env['mail.followers'].search([('res_id','=',rec.id),('res_model','=','sale.order.line'),('partner_id','=',partner_id.id)]):
                follower_id = self.env['mail.followers'].sudo().create({
            'res_id':rec.id,
            'res_model':'sale.order.line',
            'partner_id':partner_id.id

                })
    def send_mail_less(self):
        resConfig = self.env['res.config.settings']
        if resConfig.get_mp_global_field_value("enable_notify_seller_on_new_order"):
            temp_id = resConfig.get_mp_global_field_value("notify_seller_on_new_order_m_tmpl_id")
            if temp_id:
                template_obj = self.env['mail.template'].browse(temp_id)
                for order in self:
                    seller_objs = order.order_line.mapped('marketplace_seller_id')
                    for seller in seller_objs:
                        template_obj.with_context(seller=seller).with_company(self.env.company).send_mail(order.id, True)

    @api.model
    def _read_group_fill_results( self, domain, groupby, remaining_groupbys,
        aggregated_fields, read_group_order=None):
        state_list= [None for rec in range(len(self.STATES))]
        list_state = [state[0] for state in self.STATES]
        if groupby == 'marketplace_state':
            for result in aggregated_fields:
                state = result['marketplace_state']
                state_list[list_state.index(state)]=result
                if state in ['new','cancel','done']:
                    result['__fold'] = True
            state_list = [result for result in state_list if result != None ]
            aggregated_fields = state_list
        return super(SaleOrderLine, self)._read_group_fill_results(domain, groupby, remaining_groupbys,
            aggregated_fields, read_group_order)

    # Compute functions
    @api.depends('create_date')
    def _compute_create_year(self):
        for sol in self:
            sol.create_year = sol.create_date.year

    @api.depends('order_id.procurement_group_id')
    def _compute_seller_picking_ids(self):
        for sol in self:
            sol.mp_delivery_count = len(sol.mapped('order_id.picking_ids').filtered(lambda picking: picking.marketplace_seller_id.id == sol.marketplace_seller_id.id))

    def action_mark_done(self):
        """ Mark marketplace state to done"""
        for rec in self:
            if rec.marketplace_state == "shipped":
                rec.order_id.sudo().action_so_done()
            elif rec.product_type == 'service' and rec.marketplace_state =='approved':
                rec.order_id.sudo().action_so_done()

    
    def action_mass_approve(self):
        """ Mark marketplace state to Approve"""
        for rec in self:
            if rec.marketplace_state == "pending":
                rec.button_approve_ol()
            else:
                rec.button_approve_ol()

    def action_mass_confirm(self):
        """ Mark marketplace state to Confirm"""
        for rec in self:
            if rec.marketplace_state == "new":
                rec.sudo().mass_confirm_sale_order_line()
            else:
                rec.sudo().mass_confirm_sale_order_line()
   
    def action_view_delivery(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env.ref('odoo_marketplace.marketplace_stock_picking_action').sudo().read()[0]

        pickings = self.mapped('order_id.picking_ids').filtered(lambda picking: picking.marketplace_seller_id.id == self.marketplace_seller_id.id)
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            action['views'] = [(self.env.ref('odoo_marketplace.marketplace_picking_stock_modified_form_view').id, 'form')]
            action['res_id'] = pickings.id
        return action

    def action_view_sol_seller_payment(self):
        """Method to show Seller payments and change domain"""
        self.ensure_one()
        seller_payment_objs = self.sudo().order_id.invoice_ids.mapped('seller_payment_ids').filtered(lambda sp: sp.seller_id.id == self.marketplace_seller_id.id)
        action = self.env.ref('odoo_marketplace.wk_seller_payment_action').sudo().read()[0]
        if len(seller_payment_objs) > 1:
            action['domain'] = [('id', 'in', seller_payment_objs.ids)]
        elif len(seller_payment_objs) == 1:
            action['views'] = [(self.env.ref('odoo_marketplace.wk_seller_payment_form_view').id, 'form')]
            action['res_id'] = seller_payment_objs.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def button_cancel(self):
        """ Method to cancel sale order line"""
        for rec in self:
            pickings = rec.mapped('order_id.picking_ids').filtered(lambda picking: picking.marketplace_seller_id.id == rec.marketplace_seller_id.id)
            pickings.action_cancel()
            rec.sudo().marketplace_state = "cancel"
            if rec.order_id.state != 'cancel':
                rec.order_id._action_cancel()

    def confirm_sale_order_line(self):
        """ Method to confirm sale order line"""
        for rec in self:
            if rec.order_id.state == 'sale':
                rec.write({'marketplace_state':'pending'})
            else:
                rec.order_id.action_confirm()

    def mass_confirm_sale_order_line(self):
        for rec in self:  
            rec.sudo().marketplace_state = "pending"
            
    def button_approve_ol(self):
        """ Method to approve sale order line"""
        resConfig = self.order_id.env['res.config.settings']
        temp_id= resConfig.get_mp_global_field_value("notify_admin_on_no_qty")
        template_obj_qty = self.env['mail.template'].browse(temp_id)
        for rec in self: 
            rec.sudo().marketplace_state = "approved"
            rec._adding_followers()

            record=rec.marketplace_seller_id
            is_allow =record.allow_min_qty_notification
            set_min_qty = record.set_min_qty
            if is_allow:
                seller = rec.marketplace_seller_id
                product = rec.product_id
                warehouse_id = seller.get_seller_global_fields("warehouse_id")
                qty_available = product.with_context(warehouse=warehouse_id).qty_available 
                action_id = self.env.ref('odoo_marketplace.mp_product_product_action')
                if(int(qty_available))<= int(set_min_qty) and resConfig.get_mp_global_field_value("enable_notify_admin_on_no_qty"): 
                    template_obj_qty.with_context(action_id=action_id).with_company(self.env.company).send_mail(rec.id, True)

    def _prepare_procurement_values(self, group_id=False):
        values = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        """ Prepare specific key for moves or other components that will be created from a stock rule
        comming from an orderpoint."""
        self.ensure_one()
        marketplace_seller_obj = self.marketplace_seller_id
        if marketplace_seller_obj:
            seller_warehouse_id = marketplace_seller_obj.get_seller_global_fields('warehouse_id')
            if seller_warehouse_id:
                seller_warehouse_obj = self.env['stock.warehouse'].browse(seller_warehouse_id)
                values["warehouse_id"] = seller_warehouse_obj
        return values
    
def new_cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
    values = super(WebsiteSaleStock, self)._cart_update(product_id=product_id,line_id=line_id,add_qty=add_qty,set_qty=set_qty,**kwargs)    
    line_id = values.get('line_id')

    for line in self.order_line:
        if  not line.product_id.allow_out_of_stock_order:
            if line.product_id.marketplace_seller_id and line.product_id.is_storable == True:
                warehouse_id = self.warehouse_id.id
                seller_obj = line.marketplace_seller_id
                if seller_obj:
                    seller_warehouse_id = seller_obj.get_seller_global_fields("warehouse_id")
                    if seller_warehouse_id:
                        warehouse_id = seller_warehouse_id
                cart_qty = sum(self.order_line.filtered(lambda p: p.product_id.id == line.product_id.id).mapped('product_uom_qty'))
                available_qty = line.product_id.with_context(warehouse=warehouse_id).virtual_available
                if cart_qty > available_qty and (line_id == line.id):
                    mp_qty = available_qty - cart_qty
                    new_val = super(WebsiteSaleStock, self)._cart_update(product_id=line.product_id.id, line_id=line.id, add_qty=mp_qty, set_qty=0, **kwargs)
                    values.update(new_val)

                    # Make sure line still exists, it may have been deleted in super()_cartupdate because mp_qty can be <= 0
                    if line.exists() and new_val['quantity']:
                        line.shop_warning = _('You ask for %s products but only %s is available') % (cart_qty, new_val['quantity'])
                        values['warning'] = line.shop_warning
                    else:
                        self.shop_warning = _("Some products became unavailable and your cart has been updated. We're sorry for the inconvenience.")
                        values['warning'] = self.shop_warning
            else:
                cart_qty = sum(self.order_line.filtered(lambda p: p.product_id.id == line.product_id.id).mapped('product_uom_qty'))
                if cart_qty > line.product_id.with_context(warehouse=self.warehouse_id.id).free_qty and (line_id == line.id):
                    qty = line.product_id.with_context(warehouse=self.warehouse_id.id).free_qty - cart_qty
                    new_val = super(SaleOrder, self)._cart_update(product_id=line.product_id.id, line_id=line.id, add_qty=qty, set_qty=0, **kwargs)
                    values.update(new_val)

                    # Make sure line still exists, it may have been deleted in super()_cartupdate because qty can be <= 0
                    if line.exists() and new_val['quantity']:
                        line.shop_warning = _('You ask for %s products but only %s is available') % (cart_qty, new_val['quantity'])
                        values['warning'] = line.shop_warning
                    else:
                        self.shop_warning = _("Some products became unavailable and your cart has been updated. We're sorry for the inconvenience.")
                        values['warning'] = self.shop_warning
    return values

WebsiteSaleStock._cart_update = new_cart_update
