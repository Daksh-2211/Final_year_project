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

import logging
from odoo import api, fields, models
from odoo.http import request
_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def _get_seller_sale_order_ids(self, seller_so_ids=[]):
        if seller_so_ids:
            seller_so_obj = request.env['sale.order'].sudo().browse(seller_so_ids).exists()
            seller_so_obj = seller_so_obj.filtered(lambda s:s.state == 'draft')
            if seller_so_obj:
                seller_so_ids = seller_so_obj.ids
                return seller_so_ids
        return None

    def update_seller_so_ids(self, partner):
        seller_so_ids = request.session.get('seller_so_ids')
        if seller_so_ids:
            seller_so_obj = self.env['sale.order'].sudo().browse(seller_so_ids).exists()
            public_so_objs = seller_so_obj.filtered(lambda so: so.partner_id.id != partner.id)
            addr = partner.address_get(['delivery', 'invoice'])
            public_so_objs.write({
                'partner_id': partner.id,
                'partner_invoice_id': addr['invoice'],
                'partner_shipping_id': addr['delivery'],
            })


    def sale_get_order(self, force_create=False, code=None, seller_id=False):
        request.session['seller_so_ids'] = self._get_seller_sale_order_ids(request.session.get('seller_so_ids'))

        if not seller_id:
            seller_id = self._context.get('seller_id')
        if seller_id:

            # to change pricelist for public user
            update_pricelist = False
            pricelist_id = request.session.get('website_sale_current_pl') or self._get_current_pricelist().id

            partner = self.env.user.partner_id
            seller_so_id = False
            is_user_public = request.env.user.has_group('base.group_public')

            # check if sale order of this seller exist in session
            seller_so_ids = request.session.get('seller_so_ids')
            if seller_so_ids:
                seller_so_obj = request.env['sale.order'].sudo().browse(seller_so_ids).exists()
                seller_so_id = seller_so_obj.filtered(lambda o: o.marketplace_seller_id.id == seller_id)
                seller_so_id = seller_so_id[0] if len(seller_so_id) > 1 else seller_so_id

            # if seller sale order id found in session return order
            if seller_so_id:
                sale_order = request.env['sale.order'].sudo().browse(seller_so_id.id)
                previous_pricelist = sale_order.pricelist_id.id

                # code for promo code to update pricelist

                if pricelist_id != previous_pricelist:
                    update_pricelist = True
                # update the pricelist
                if update_pricelist:
                    request.session['website_sale_current_pl'] = pricelist_id
                    sale_order.write({'pricelist_id': pricelist_id})
                    sale_order._recompute_prices()
                return request.env['sale.order'].sudo().browse(seller_so_id.id)

            # if seller sale order id not found in session then search in all so ids of partner and update in session
            else:
                if not is_user_public and partner.sale_order_ids and request.website.partner_id.id != partner.id:
                    seller_so_id = partner.sale_order_ids.filtered(lambda o: o.state == 'draft' and o.marketplace_seller_id.id == seller_id)
                    if seller_so_id:
                        if seller_so_ids:
                            seller_so_id = seller_so_id[0] if len(seller_so_id) > 1 else seller_so_id
                            seller_so_ids.append(seller_so_id.id)
                        else:
                            seller_so_ids = [seller_so_id.id]
                        request.session.pop('seller_so_ids', None)
                        request.session['seller_so_ids'] = seller_so_ids
                        sale_order = request.env['sale.order'].sudo().browse(seller_so_id.id)

                        previous_pricelist = sale_order.pricelist_id

                        if sale_order.pricelist_id != previous_pricelist:
                            update_pricelist = True

                        # update the pricelist
                        if update_pricelist:
                            request.session['website_sale_current_pl'] = pricelist_id
                            sale_order.write({'pricelist_id': pricelist_id})
                            sale_order._recompute_prices()

                        return request.env['sale.order'].sudo().browse(seller_so_id.id)

            # if no sale order of seller found in session and in previous order of partner then create new so for this seller and update in session
            session_sale_order_id = request.session.get('sale_order_id')
            last_order = partner.last_website_so_id

            # make session and last sale order id false so that a new order can be created for this seller
            request.session['sale_order_id'] = None
            partner.last_website_so_id = False
            seller_so_id = super(Website, self).sale_get_order(force_create=force_create)

            if seller_so_id:
                seller_so_id.marketplace_seller_id = seller_id  
                # update warehouse of seller in seller order
                seller_obj = self.env["res.partner"].sudo().browse(seller_id)
                warehouse_id = seller_obj.get_seller_global_fields("warehouse_id")
                if warehouse_id:
                    seller_so_id.warehouse_id = warehouse_id

                if seller_so_ids:
                    seller_so_ids.append(seller_so_id.id)
                else:
                    seller_so_ids = [seller_so_id.id]
                request.session['seller_so_ids'] = seller_so_ids
                # update the last website so id and so id session for admin cart
                request.session['sale_order_id'] = session_sale_order_id
                partner.last_website_so_id = last_order
                return request.env['sale.order'].sudo().browse(seller_so_id.id)

        so = super(Website, self).sale_get_order(force_create=force_create)
        if so and so.state != 'draft':
            so = super(Website, self).sale_get_order(force_create=force_create)
        if so and not so.marketplace_seller_id:
            request.session['admin_so'] = request.session['sale_order_id']
        return so

    def sale_reset(self, order_id=None):
        if order_id:
            seller_so_ids = request.session.get('seller_so_ids') or []
            seller_so_ids.remove(order_id) if order_id in seller_so_ids else seller_so_ids
            if seller_so_ids:
                request.session.update({
                    'seller_so_ids': seller_so_ids,
                    'sale_transaction_id': False,
                    'website_sale_current_pl': False,
                })
                return
        else:
            order = request.env['sale.order'].sudo().browse(request.session.get('sale_order_id') or False)
            if order.marketplace_seller_id:
                seller_so_ids = request.session.get('seller_so_ids') or []
                seller_so_ids.remove(order.id) if order.id in seller_so_ids else seller_so_ids
                request.session.update({'seller_so_ids' : seller_so_ids,})
            else:
                request.session.update({'admin_so':None,})
            res = super(Website, self).sale_reset()
            return res

    def get_admin_so_ids(self):
        admin_so = request.session.get('admin_so',False)
        is_user_public = request.env.user.has_group('base.group_public')
        if admin_so:
            so = self.env['sale.order'].sudo().browse(admin_so).exists()
            so =  so.filtered(lambda x: x.partner_id.id == request.env.user.partner_id.id)
            if so.id:
                request.session.update(admin_so=so.ids)
                return so if so.state=='draft' else False
        if not is_user_public:
            domain = [('state','=','draft'),('marketplace_seller_id','in',[False,None]),('partner_id','=',request.env.user.partner_id.id)]
            so =  self.env['sale.order'].sudo().search(domain,order='date_order desc',limit=1)
            request.session.update(admin_so=so.ids)
            return so if len(so)>0 else False
        return False

    def get_seller_so_ids(self):
        seller_so_ids = request.session.get('seller_so_ids',False)
        is_user_public = request.env.user.has_group('base.group_public')
        if seller_so_ids and len(seller_so_ids)>0:
            so = self.env['sale.order'].sudo().browse(seller_so_ids).exists()
            so  = so.filtered(lambda x:(x.state == 'draft'and x.partner_id.id == request.env.user.partner_id.id))
            if len(so)>0:
                request.session.update(seller_so_ids=so.ids)
                return so
        if not is_user_public:
            domain  = [('state','=','draft'),('partner_id','=',request.env.user.partner_id.id)]
            so = request.env['sale.order'].sudo().search(domain)
            so = so.filtered(lambda x:x.marketplace_seller_id)
            request.session.update(seller_so_ids=so.ids)
            return so
        return False

    def wk_get_website_cart_qty(self):
        admin_so = self.get_admin_so_ids()
        seller_so = self.get_seller_so_ids()
        admin_qty = admin_so.cart_quantity if admin_so else 0
        seller_qty = sum(seller_so.mapped('cart_quantity')) if seller_so else 0
        total_qty = admin_qty + seller_qty
        return total_qty
