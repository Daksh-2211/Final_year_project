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

from odoo import http,fields
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.odoo_marketplace.controllers.main import AuthSignupHome
from odoo.addons.web.controllers.utils import ensure_db
from odoo.addons.odoo_marketplace.controllers.main import ActionInherit
import logging,json
_logger = logging.getLogger(__name__)
from odoo.tools.json import scriptsafe as json_scriptsafe

class WebsiteSale(WebsiteSale):

    @http.route(['/shop/change_pricelist/<model("product.pricelist"):pl_id>'], type='http', auth="public", website=True)
    def pricelist_change(self, pl_id, **post):

        if (pl_id.selectable or pl_id == request.env.user.partner_id.property_product_pricelist) \
                and request.website.is_pricelist_available(pl_id.id):

            request.session['website_sale_current_pl'] = pl_id.id
            request.website.sale_get_order()
            seller_so_ids = request.session.get("seller_so_ids")
            seller_so_ids = request.website._get_seller_sale_order_ids(seller_so_ids) or False
            seller_so_ids = request.env['sale.order'].sudo().browse(seller_so_ids)
            if seller_so_ids:
                for o in seller_so_ids:
                    seller_id = o.marketplace_seller_id.id or False
                    request.session['website_sale_current_pl'] = pl_id.id
                    request.website.with_context(seller_id = seller_id).sale_get_order()
        return request.redirect(request.httprequest.referrer or '/shop')

    @http.route(['/shop/pricelist'], type='http', auth="public", website=True)
    def pricelist(self, promo, **post):
        redirect = post.get('r', '/shop/cart')
        pricelist = request.env['product.pricelist'].sudo().search([('code', '=', promo)], limit=1)
        if not pricelist:
            return request.redirect("%s?code_not_available=1" % redirect)
        if not pricelist or (pricelist and not request.website.is_pricelist_available(pricelist.id)):
            return request.redirect("%s?code_not_available=1" % redirect)

        request.website.sale_get_order()
        return request.redirect(redirect)

    @http.route()
    def cart(self, access_token=None, revive='', **post):
        res = super(WebsiteSale, self).cart(access_token=access_token,revive=revive,post=post)

        request.session['sale_order_id'] = request.session['admin_so'] if request.session.get('admin_so') else None
        values = {}
        seller_so_ids = request.session.get("seller_so_ids")
        # seller_so_ids = request.website.get_seller_so_ids()
        if seller_so_ids:
            seller_so_ids = request.website._get_seller_sale_order_ids(seller_so_ids) or False
            seller_so_ids = request.env['sale.order'].sudo().browse(seller_so_ids)
        #     # do same for all seller orders
            for o in seller_so_ids:
                from_currency = o.company_id.currency_id
                to_currency = o.pricelist_id.currency_id
                compute_currency = lambda price: from_currency._convert(
                    price, to_currency, request.env.user.company_id, fields.Date.today())
        values.update({
            'website_sale_order': request.website.sale_get_order(),
            'suggested_products': [],
            'seller_so_ids':seller_so_ids if seller_so_ids else False,
        })
        if seller_so_ids:
            for o in seller_so_ids:
                _order = o
                if not request.env.context.get('pricelist'):
                    _order = o.with_context(pricelist=o.pricelist_id.id)
        res.qcontext.update(values)

        total_cart_qty = request.website.wk_get_website_cart_qty()

        request.session['website_sale_cart_quantity'] = total_cart_qty
        return res

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0,
        product_custom_attribute_values=None, no_variant_attribute_values=None,
        express=False, **kw):
        _logger.info("SELLER WISE CART UPDATE ==================")
        prod_obj = request.env['product.product'].sudo().browse(int(product_id))
        seller_id = prod_obj.sudo().marketplace_seller_id.id if prod_obj.sudo().marketplace_seller_id else False

        sale_order = request.website.with_context(seller_id=seller_id).sale_get_order(force_create=True)

        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw
        )

        total_cart_qty = request.website.wk_get_website_cart_qty()
        request.session['website_sale_cart_quantity'] = total_cart_qty
        if kw.get('express') and seller_id:
            return request.redirect("/shop/checkout?express=1&seller=%s"%str(seller_id))
        if kw.get('express'):
            return request.redirect("/shop/checkout?express=1")

        return request.redirect("/shop/cart")

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True,
        product_custom_attribute_values=None, no_variant_attribute_values=None, **kw
    ):
        prod_obj = request.env['product.product'].browse(int(product_id))
        seller_id = prod_obj.sudo().marketplace_seller_id.id if prod_obj.sudo().marketplace_seller_id else False

        if line_id:
            order = request.env['sale.order.line'].sudo().browse(int(line_id)).order_id
        else:
            order = request.website.with_context(seller_id=seller_id).sale_get_order(force_create=True)
        self.wk_update_order_date(order)
        if order.state != 'draft':
            request.website.sale_reset(order_id= order.id if order.marketplace_seller_id else None)
            admin_qty = request.website.sale_get_order() and request.website.sale_get_order().cart_quantity or 0
            sellers_qty = 0
            seller_so_ids = request.session.get("seller_so_ids")
            if seller_so_ids:
                request.website._get_seller_sale_order_ids(seller_so_ids)
                seller_so_ids = request.env['sale.order'].sudo().browse(seller_so_ids)
                sellers_qty = sum(seller_so_ids.mapped('cart_quantity'))
            total_cart_qty = admin_qty + sellers_qty
            return {'total_cart_qty': total_cart_qty,'no_line':True,}
        if product_custom_attribute_values:
            product_custom_attribute_values = json_scriptsafe.loads(product_custom_attribute_values)

        if no_variant_attribute_values:
            no_variant_attribute_values = json_scriptsafe.loads(no_variant_attribute_values)

        value = order._cart_update(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw)
        if not order.cart_quantity:
            request.website.sale_reset(order_id= order.id if order.marketplace_seller_id else None)
            admin_qty = request.website.sale_get_order() and request.website.sale_get_order().cart_quantity or 0
            sellers_qty = 0
            seller_so_ids = request.session.get("seller_so_ids")
            if seller_so_ids:
                request.website._get_seller_sale_order_ids(seller_so_ids)
                seller_so_ids = request.env['sale.order'].sudo().browse(seller_so_ids)
                sellers_qty = sum(seller_so_ids.mapped('cart_quantity'))
            total_cart_qty = admin_qty + sellers_qty
            return {'total_cart_qty': total_cart_qty, 'no_line':True,}

        # order = request.website.sale_get_order(seller_id= seller_id)
        website_sale_order = request.website.get_admin_so_ids()
        value['notification_info'] = self._get_cart_notification_information(order, [value['line_id']])
        value['cart_ready'] = order._is_cart_ready()
        seller_so_ids = request.website.get_seller_so_ids()
        seller_so = seller_so_ids.filtered(lambda o: len(o.website_order_line)>0) if seller_so_ids else False
        admin_cart_qty = website_sale_order and website_sale_order.exists() and website_sale_order.cart_quantity or 0
        seller_cart_qty = seller_so and sum(seller_so.mapped('cart_quantity')) or 0
        value['cart_quantity'] = admin_cart_qty + seller_cart_qty
        from_currency = order.company_id.currency_id
        to_currency = order.pricelist_id.currency_id

        if not display:
            return value

        # count total cart quantity
        admin_qty = request.website.sale_get_order() and request.website.sale_get_order().cart_quantity or 0
        sellers_qty = 0
        seller_so_ids = request.session.get("seller_so_ids")
        if seller_so_ids:
            request.website._get_seller_sale_order_ids(seller_so_ids)
            seller_so_ids = request.env['sale.order'].sudo().browse(seller_so_ids)
            sellers_qty = sum(seller_so_ids.mapped('cart_quantity'))
        total_cart_qty = admin_qty + sellers_qty
        value['total_cart_qty'] = total_cart_qty
        value['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template("website_sale.cart_lines", {
            'website_sale_order': order,
            'date': fields.Date.today(),
            'compute_currency': lambda price: from_currency._convert(
                price, to_currency, order.company_id, fields.Date.today()),
            'suggested_products': order._cart_accessories()
            })

        value['website_sale.total'] = request.env['ir.ui.view']._render_template("website_sale.total", {
            'website_sale_order': order,
            'compute_currency': lambda price: from_currency._convert(
                price, to_currency, request.env.user.company_id, fields.Date.today()),
        })
        return value

    @http.route(['/seller/wise/checkout'], type="json", auth="public", website=True)
    def _seller_wise_checkout(self, seller_id):
        seller_id = int(seller_id) if type(seller_id)==int else False
        order = request.website.with_context(seller_id=seller_id).sale_get_order()
        if seller_id:
            request.session['sale_order_id'] = order.id

    @http.route()
    def shop_payment(self, **post):
        res = super(WebsiteSale, self).shop_payment(**post)
        res.qcontext.update({'show_in_cart': True,})
        if post.get('code_not_available'):
            res.qcontext.update({'code_not_available': True,})
        return res

    @http.route()
    def address(self, **kw):
        sale_order_id = request.session.get('sale_order_id')
        res = super(WebsiteSale, self).address(**kw)
        request.session['sale_order_id'] = sale_order_id
        return res

    @http.route()
    def cart_quantity(self):
        if 'website_sale_cart_quantity' not in request.session:
            return request.website.wk_get_website_cart_qty()
        return request.session['website_sale_cart_quantity']

    @http.route()
    def shop_payment_validate(self, transaction_id=None, sale_order_id=None, **post):
        last_sale_order_id = request.session.get('sale_order_id')
        res = super().shop_payment_validate(transaction_id=transaction_id, sale_order_id=sale_order_id, **post)
        if last_sale_order_id and not request.session.get('sale_order_id'):
            order = request.env['sale.order'].sudo().browse(last_sale_order_id).exists()
            if order.state == 'draft' and order.website_order_line:
                if order.marketplace_seller_id:
                    seller_so_ids = request.session.get('seller_so_ids', [])
                    seller_so_ids.append(last_sale_order_id)
                    request.session['seller_so_ids'] = seller_so_ids
                else:
                    request.session['sale_order_id'] = last_sale_order_id
        return res

    def wk_update_order_date(self, order):
        if order and order.state == 'draft' and not order.order_line :
            order.write({
                'date_order': fields.Datetime.now()
            })

class AuthSignupHome(AuthSignupHome):

    @http.route()
    def web_login(self, redirect=None, *args, **kw):
        ensure_db()
        response = super(AuthSignupHome, self).web_login(redirect=redirect, *args, **kw)
        partner = request.env.user.partner_id
        if request.website.partner_id.id != partner.id:
            request.website.update_seller_so_ids(partner)
        return response


class MpActionInherit(ActionInherit):

    def get_allowed_module_resource(self):
        module_list = super().get_allowed_module_resource()
        module_list.append('marketplace_seller_wise_checkout')
        return module_list