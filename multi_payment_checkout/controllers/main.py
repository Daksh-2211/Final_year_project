from odoo import http, fields, _
from markupsafe import Markup
from odoo.http import request, route
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_event_sale.controllers.main import WebsiteEventSaleController
import logging
import json
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class WebsiteEventSaleCombined(WebsiteEventSaleController):
    @route()
    def registration_confirm(self, event, **post):
        response = super().registration_confirm(event, **post)

        # --- Guest Membership Dedup ---
        order = request.website.sale_get_order(force_create=False)
        is_public = request.env.user.id == request.website.user_id.id
        _logger.info(
            "Guest dedup CHECK: order=%s, is_public=%s, user=%s, post_keys=%s",
            order.name if order else None, is_public,
            request.env.user.name, list(post.keys()),
        )
        if order:
            try:
                # Extract attendee emails from post data
                attendee_emails = [
                    v.strip() for k, v in post.items()
                    if '-email' in k and v and v.strip()
                ]

                if attendee_emails:
                    # Find real partner records matching these emails
                    existing_partners = request.env['res.partner'].sudo().search([
                        ('email', 'in', attendee_emails)
                    ])

                    if existing_partners:
                        # Find membership lines in the cart
                        membership_lines = order.order_line.filtered(
                            lambda l: l.product_id.recurring_invoice
                        )
                        for mem_line in membership_lines:
                            mem_product = mem_line.product_id
                            # Check if any matched partner already has a confirmed order containing this membership product.
                            one_year_ago = fields.Datetime.now() - relativedelta(years=1)
                            existing_membership = request.env['sale.order'].sudo().search([
                                ('partner_id', 'in', existing_partners.ids),
                                ('state', 'in', ['sale', 'done']),
                                ('order_line.product_id', '=', mem_product.id),
                                ('date_order', '>', one_year_ago)
                            ], order='date_order desc', limit=1)
                            if existing_membership:
                                mem_line.sudo().unlink()
                                order.sudo().write({'plan_id': False})
                    else:
                        _logger.info("Guest dedup: no existing partners found for emails %s", attendee_emails)
                else:
                    _logger.info("Guest dedup: no attendee emails found in post")
            except Exception as e:
                _logger.error("Error in guest membership dedup: %s", str(e))

        # Add optional products to the cart if selected in the attendee modal
        optional_product_prefix = 'optional_product_'
        selected_opt_templates = [
            int(k.replace(optional_product_prefix, ''))
            for k, v in post.items()
            if k.startswith(optional_product_prefix) and v == 'on'
        ]

        if selected_opt_templates:
            order = request.website.sale_get_order(force_create=False)
            if order:
                # Calculate total tickets bought in this request
                qty = sum(1 for k in post.keys() if k.endswith('-event_ticket_id'))
                if qty > 0:
                    for tmpl_id in selected_opt_templates:
                        product = request.env['product.product'].sudo().search([('product_tmpl_id', '=', tmpl_id)],
                                                                               limit=1)
                        if product:
                            order._cart_update(
                                product_id=product.id,
                                add_qty=qty
                            )
        if response.status_code in [302, 303]:
            location = response.headers.get('Location', '')
            if '/shop/checkout' in location:
                return request.redirect('/shop/cart')
        return response

    def _prepare_event_register_values(self, event, **post):
        """Add GTM dataLayer data for begin_registration event."""
        values = super()._prepare_event_register_values(event, **post)
        # Determine price: use lowest available ticket price, or 0 for free
        tickets = event.event_ticket_ids.filtered(lambda t: not t.is_expired)
        if tickets:
            price = min(tickets.mapped('price'))
        else:
            price = 0
        currency = event.company_id.currency_id.name or request.website.currency_id.name or 'EUR'
        # Pre-serialize as JSON string for safe inline <script> rendering
        values['gtm_begin_registration_json'] = Markup(json.dumps({
            'event': 'begin_registration',
            'event_name': event.name or '',
            'event_id': str(event.id),
            'price': str(price),
            'currency': currency,
        }))
        return values

    def _get_registration_confirm_values(self, event, attendees_sudo):
        """Add GTM dataLayer data for purchase event (free ticket flow)."""
        values = super()._get_registration_confirm_values(event, attendees_sudo)
        currency = event.company_id.currency_id.name or request.website.currency_id.name or 'EUR'

        # Build GA4-compliant items array
        items = []
        total_value = 0.0
        for att in attendees_sudo:
            ticket = att.event_ticket_id
            price = ticket.price if ticket else 0.0
            total_value += price
            items.append({
                'item_name': event.name or '',
                'item_id': str(event.id),
                'price': float(price),
                'quantity': 1,
                'item_category': 'Event Registration',
                'registration_id': str(att.id),
            })

        # Single aggregated purchase event with deduplication ID
        transaction_id = 'free_%s_%s' % (event.id, '_'.join(str(a.id) for a in attendees_sudo))
        gtm_purchase = {
            'event': 'purchase',
            'event_id': 'purchase_%s' % transaction_id,
            'ecommerce': {
                'transaction_id': transaction_id,
                'value': float(total_value),
                'currency': currency,
                'items': items,
            }
        }
        values['gtm_purchase_items_json'] = Markup(json.dumps(gtm_purchase))
        return values

class WebsiteSaleCombined(WebsiteSale):

    def _prepare_shop_payment_confirmation_values(self, order):
        reward_lines = order.order_line.filtered(lambda l: l.is_reward_line)
        if not reward_lines and (order.applied_coupon_ids or order.code_enabled_rule_ids):
            order.sudo()._update_programs_and_rewards()
            if hasattr(self, '_propagate_discount_to_seller_orders'):
                self._propagate_discount_to_seller_orders(order)

        order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
        order.sudo().invalidate_recordset(['amount_total'])

        values = super()._prepare_shop_payment_confirmation_values(order)
        values.update({
            'website_sale_order': order,
        })

        # --- GTM: build single GA4-compliant purchase dataLayer event ---
        gtm_items = []
        total_value = 0.0
        # Support both regular orders and combined master orders
        order_ids = [order.id]
        if hasattr(order, 'linked_seller_order_ids') and order.linked_seller_order_ids:
            order_ids.extend(order.linked_seller_order_ids.ids)

        # Check if any of these orders have events
        all_orders = request.env['sale.order'].sudo().browse(order_ids)
        events = all_orders.mapped('order_line.event_id')

        currency = order.currency_id.name or 'EUR'

        if events:
            registrations = request.env['event.registration'].sudo().search([
                ('sale_order_id', 'in', order_ids),
                ('state', 'in', ['open', 'done']),
            ])
            for reg in registrations:
                ev = reg.event_id
                ticket = reg.event_ticket_id
                price = float(ticket.price if ticket else 0)
                total_value += price
                gtm_items.append({
                    'item_name': ev.name or '',
                    'item_id': str(ev.id),
                    'price': price,
                    'quantity': 1,
                    'item_category': 'Event Registration',
                    'registration_id': str(reg.id),
                })
            # Trigger Meta CAPI Server-Side Event
            try:
                capi_env = request.env(context=dict(
                    request.env.context,
                    client_ip=request.httprequest.remote_addr,
                    user_agent=request.httprequest.user_agent.string
                ))
                capi_env['meta.capi.service'].sudo().send_purchase_event(registrations.ids)
            except Exception as e:
                    _logger.error(f"Failed to trigger Meta CAPI for paid registration: {e}")
        else:
            # Non-event products (regular shop items)
            for line in order.order_line.filtered(lambda l: not l.is_reward_line and not l.display_type):
                price = float(line.price_unit)
                total_value += price * line.product_uom_qty
                gtm_items.append({
                    'item_name': line.product_id.name or line.name or '',
                    'item_id': str(line.product_id.id),
                    'price': price,
                    'quantity': int(line.product_uom_qty),
                    'item_category': 'Product',
                })

        # Single aggregated purchase event with deduplication ID
        transaction_id = order.name or str(order.id)
        gtm_purchase = {
            'event': 'purchase',
            'event_id': 'purchase_%s' % order.id,
            'ecommerce': {
                'transaction_id': transaction_id,
                'value': float(total_value),
                'currency': currency,
                'items': gtm_items,
            }
        }
        values['gtm_purchase_items_json'] = Markup(json.dumps(gtm_purchase))
        return values

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        sale_order_id = request.session.get('sale_last_order_id')

        if sale_order_id:
            request.session['sale_order_id'] = sale_order_id
            request.website.sale_get_order(force_create=False)

        if sale_order_id:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            if order.exists():
                tx = order.get_portal_last_transaction()
                if tx:
                    provider = tx.provider_id
                    transfer_provider = request.env.ref(
                        'payment.payment_provider_transfer',
                        raise_if_not_found=False
                    )
                    if provider == transfer_provider and tx.state in ('pending'):
                        _logger.info("Applying combined payment logic for order %s via transfer BEFORE render",
                                     order.name)
                        order._process_combined_payment(tx)
                        order.sudo().flush_recordset()
                        order.sudo().invalidate_recordset()

        response = super().shop_payment_confirmation(**post)
        return response

    @http.route(['/shop/combined_checkout'], type='http', auth="public", website=True, sitemap=False)
    def combined_checkout(self, **post):
        seller_so_ids = request.session.get('seller_so_ids') or []
        current_standard_so_id = request.session.get('sale_order_id')

        saved_coupons = []
        saved_rules = []

        if current_standard_so_id:
            standard_so = (request.env['sale.order'].sudo().browse(current_standard_so_id).exists())
            if standard_so and standard_so.state == 'draft':
                saved_coupons = standard_so.applied_coupon_ids.ids
                saved_rules = standard_so.code_enabled_rule_ids.ids

            if (standard_so and standard_so.state == 'draft' and standard_so.order_line):
                regular_lines = standard_so.order_line.filtered( lambda l: not l.is_reward_line)
                reward_lines = standard_so.order_line.filtered(lambda l: l.is_reward_line)

                # Recompute each reward line via per-line, tax-aware traversal.
                # IMPORTANT: snapshot into plain dicts BEFORE any unlink to avoid
                reward_line_snapshot = []
                for reward_line in reward_lines:
                    reward = reward_line.reward_id
                    if not reward or reward.reward_type != 'discount' or not reward.discount:
                        continue
                    reward_product = reward.discount_line_product_id
                    if not reward_product:
                        continue
                    reward_line_snapshot.append({
                        'line_id': reward_line.id,
                        'reward': reward,
                        'reward_product': reward_product,
                        'reward_label': (
                            getattr(reward, 'description', None)
                            or getattr(reward, 'reward_description', None)
                            or str(reward.id)
                        ),
                        'identifier_code': str(reward.id),
                        'tax_groups': standard_so._group_discounts_by_tax(
                            regular_lines, reward, reward_line
                        ),
                    })

                # Unlink all old reward lines in one batch
                lines_to_unlink = request.env['sale.order.line'].sudo().browse(
                    [s['line_id'] for s in reward_line_snapshot]
                ).exists()
                if lines_to_unlink:
                    lines_to_unlink.sudo().unlink()

                # Now create correct tax-grouped reward lines
                for snap in reward_line_snapshot:
                    tax_groups = snap['tax_groups']
                    _logger.info(
                        "combined_checkout STEP0: so=%s reward=%s tax_groups=%s",
                        standard_so.name, snap['reward'].id,
                        {str(list(k)): v['amount'] for k, v in tax_groups.items()},
                    )
                    if not tax_groups:
                        _logger.info(
                            "combined_checkout STEP0: No discount → skipping reward on %s",
                            standard_so.name,
                        )
                        continue
                    standard_so._upsert_reward_lines(
                        standard_so, snap['reward'], snap['reward_product'],
                        snap['reward_label'], snap['identifier_code'], tax_groups,
                    )

                # Re-read after potential unlinks/creates
                reward_lines = standard_so.order_line.filtered(lambda l: l.is_reward_line)

                lines_by_seller = {}

                # 1. Map regular products by seller
                for line in regular_lines:
                    seller = line.product_id.marketplace_seller_id
                    seller_id = seller.id if seller else 'admin'

                    if seller_id not in lines_by_seller:
                        lines_by_seller[seller_id] = request.env['sale.order.line']
                    lines_by_seller[seller_id] += line

                if not lines_by_seller:
                    return request.redirect('/shop/cart')

                primary_key = list(lines_by_seller.keys())[0]

                # Distribute reward lines by seller:
                # Each reward line already carries its correct tax group. We assign it to the seller whose products share the same taxes.
                for reward in reward_lines:
                    r = reward.reward_id
                    target_products = (
                        getattr(r, 'discount_specific_product_ids', False)
                        or getattr(r, 'discount_product_ids', False)
                    ) if r else False

                    if target_products:
                        eligible_lines = regular_lines.filtered(
                            lambda l: l.product_id.id in target_products.ids
                        )
                    else:
                        eligible_lines = regular_lines

                    # Find the seller(s) whose product lines share this reward line's tax fingerprint
                    reward_tax_key = frozenset(reward.tax_id.ids)

                    # Build mapping: tax_key -> seller_id for eligible lines
                    tax_key_to_seller = {}
                    for el in eligible_lines:
                        s_id = (
                            el.product_id.marketplace_seller_id.id
                            if el.product_id.marketplace_seller_id
                            else 'admin'
                        )
                        key = frozenset(el.tax_id.ids)
                        if key not in tax_key_to_seller:
                            tax_key_to_seller[key] = s_id

                    # Find the seller for this reward line's tax group
                    assigned_seller = tax_key_to_seller.get(reward_tax_key, primary_key)

                    if assigned_seller not in lines_by_seller:
                        lines_by_seller[assigned_seller] = request.env['sale.order.line']
                    lines_by_seller[assigned_seller] += reward

                # Primary Order
                seller_ids_found = list(lines_by_seller.keys())
                primary_key = seller_ids_found[0]

                if primary_key != 'admin':
                    standard_so.marketplace_seller_id = primary_key

                has_sub_primary = lines_by_seller[primary_key].filtered(lambda l: l.product_id.recurring_invoice and not l.is_reward_line)
                if has_sub_primary:
                    pricings = (
                        has_sub_primary[0].product_id.sudo()
                        .product_subscription_pricing_ids
                    )
                    standard_so.plan_id = pricings[0].plan_id.id if pricings else False
                else:
                    standard_so.plan_id = False

                if standard_so.id not in seller_so_ids:
                    seller_so_ids.append(standard_so.id)

                # Split Orders
                for s_key in seller_ids_found[1:]:
                    seller_id_val = s_key if s_key != 'admin' else False
                    new_so = standard_so.copy({
                        'order_line': False,
                        'marketplace_seller_id': seller_id_val,
                        'client_order_ref': f"Split from {standard_so.name}",
                        'plan_id': False,
                    })

                    lines_to_move = lines_by_seller[s_key].exists()
                    lines_to_move.sudo().write({'order_id': new_so.id})

                    has_membership = lines_to_move.filtered(lambda l: l.product_id.recurring_invoice and not l.is_reward_line)
                    if has_membership:
                        pricings = has_membership[0].product_id.sudo().product_subscription_pricing_ids
                        if pricings:
                            new_so.plan_id = pricings[0].plan_id.id

                    regs = request.env['event.registration'].sudo().search([('sale_order_line_id', 'in', lines_to_move.ids)])
                    regs.sudo().write({'sale_order_id': new_so.id})
                    seller_so_ids.append(new_so.id)

        # 2. CLEANUP & PREP
        final_list = []
        orders_map = {}
        # Refresh browser on the updated list
        all_orders = request.env['sale.order'].sudo().browse(seller_so_ids).exists()

        for order in all_orders:
            seller_key = order.marketplace_seller_id.id if order.marketplace_seller_id else 'admin'

            if seller_key in orders_map:
                target_order = orders_map[seller_key]

                lines_to_merge = order.order_line
                lines_to_merge.sudo().write({'order_id': target_order.id})

                regs = request.env['event.registration'].sudo().search([
                    ('sale_order_line_id', 'in', lines_to_merge.ids)
                ])
                regs.sudo().write({'sale_order_id': target_order.id})

                order._action_cancel()
            else:
                orders_map[seller_key] = order
                final_list.append(order.id)

        seller_so_ids = final_list
        request.session['seller_so_ids'] = seller_so_ids

        if not seller_so_ids:
            return request.redirect('/shop/cart')

        # orders = request.env['sale.order'].sudo().browse(seller_so_ids).exists()
        orders = request.env['sale.order'].sudo().search([('id', 'in', seller_so_ids)])
        orders = orders.filtered(lambda o: o.state in ['draft', 'sent'] and len(o.order_line) > 0)

        if not orders:
            return request.redirect('/shop/cart')

        if len(orders) == 1:
            request.session['sale_order_id'] = orders.id
            request.session['master_aggregator_so_id'] = None
            return request.redirect('/shop/checkout')

        # 3. MASTER AGGREGATOR CREATION
        partner = request.env.user.partner_id
        master_order_id = request.session.get('master_aggregator_so_id')
        master_order = request.env['sale.order'].sudo().browse(master_order_id) if master_order_id else False

        if not master_order or not master_order.exists() or master_order.state != 'draft':
            master_order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'is_combined_payment_order': True,
                'website_id': request.website.id,
            })

        if saved_coupons or saved_rules:
            master_order.sudo().write({
                'applied_coupon_ids': [(6, 0, saved_coupons)],
                'code_enabled_rule_ids': [(6, 0, saved_rules)],
            })

        for order in orders:
            for coupon_id in order.applied_coupon_ids.ids:
                if coupon_id not in master_order.applied_coupon_ids.ids:
                    master_order.sudo().write({
                        'applied_coupon_ids': [(4, coupon_id)],
                    })
            for rule_id in order.code_enabled_rule_ids.ids:
                if rule_id not in master_order.code_enabled_rule_ids.ids:
                    master_order.sudo().write({
                        'code_enabled_rule_ids': [(4, rule_id)],
                    })

        for order in orders:
            reward_lines = order.order_line.filtered(lambda l: l.is_reward_line)
            if reward_lines:
                _logger.info(
                    "combined_checkout: stripping %d reward lines from %s before master copy",
                    len(reward_lines), order.name,
                )
                reward_lines = order.order_line.filtered(lambda l: l.is_reward_line).exists()
                if reward_lines:
                    reward_lines.sudo().unlink()

        master_order.linked_seller_order_ids = [(6, 0, orders.ids)]

        master_order.order_line.sudo().unlink()

        master_plan_id = False

        for order in orders:
            for line in order.order_line:
                if line.product_id.recurring_invoice and not master_plan_id:
                    pricings = line.product_id.product_subscription_pricing_ids
                    if pricings:
                        master_plan_id = pricings[0].plan_id.id

                line_vals = {
                    'order_id': master_order.id,
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.name,
                    'product_uom_qty': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'tax_id': [(6, 0, line.tax_id.ids)],
                    'discount': line.discount,
                    'is_reward_line': False,
                    'reward_id': False,
                    'reward_identifier_code': False,
                }

                if line.event_id:
                    line_vals.update({
                        'event_id': line.event_id.id,
                        'event_ticket_id': line.event_ticket_id.id
                    })

                request.env['sale.order.line'].sudo().create(line_vals)

                if line.product_id.recurring_invoice and not line.is_reward_line and not master_plan_id:
                    pricings = line.product_id.sudo().product_subscription_pricing_ids
                    if pricings:
                        master_plan_id = pricings[0].plan_id.id

        if master_plan_id:
            master_order.sudo().write({'plan_id': master_plan_id})

        if master_order.applied_coupon_ids:
            _logger.info(
                "combined_checkout: creating and propagating rewards on master %s for coupons %s",
                master_order.name, master_order.applied_coupon_ids.mapped('code'),
            )
            master_order._create_and_propagate_rewards()

        request.session['sale_order_id'] = master_order.id
        request.session['master_aggregator_so_id'] = master_order.id

        return request.redirect('/shop/checkout')

    @http.route('/shop/payment/validate', type='http', auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        # 1. Get the Order
        if sale_order_id is None:
            sale_order_id = request.session.get('sale_last_order_id')

        if sale_order_id:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            tx = order.get_portal_last_transaction()

            if tx and tx.state in ['done', 'authorized']:
                return request.redirect('/shop/confirmation')

            if order.exists() and order.is_combined_payment_order and order.state == 'cancel':
                return request.redirect('/shop/confirmation')

        return super().shop_payment_validate(sale_order_id=sale_order_id, **post)



class WebsiteSaleCartFix(WebsiteSale):

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, *args, **kwargs):
        res = super().cart_update_json(*args, **kwargs)
        if hasattr(self, '_get_cart_notification_information') and isinstance(res, dict) and 'notification_info' not in res:
            res['notification_info'] = {'lines': []}
        return res

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        order = request.website.sale_get_order()
        if order and order.is_combined_payment_order:
            request.session['sale_order_id'] = None
            if order.state == 'draft':
                for inv in order.invoice_ids:
                    if inv.state != 'cancel':
                        if inv.state == 'posted':
                            inv.button_draft()
                        inv.button_cancel()
                order._action_cancel()

        seller_so_ids = request.session.get('seller_so_ids') or []

        if seller_so_ids and any(isinstance(x, list) for x in seller_so_ids):
            flat_ids = []
            for item in seller_so_ids:
                if isinstance(item, list):
                    flat_ids.extend(item)
                else:
                    flat_ids.append(item)
            seller_so_ids = flat_ids

        if seller_so_ids:
            # orders = request.env['sale.order'].sudo().browse(seller_so_ids).exists()
            orders = request.env['sale.order'].sudo().search([('id','in',seller_so_ids)])
            event_orders = orders.filtered(lambda o: any(line.event_id for line in o.order_line))

            pure_seller_orders = orders - event_orders

            if event_orders:
                main_cart = event_orders[0]

                main_cart.sudo().write({'marketplace_seller_id': False})

                for other_so in event_orders[1:]:
                    other_so.order_line.sudo().write({'order_id': main_cart.id})

                    regs = request.env['event.registration'].sudo().search([
                        ('sale_order_line_id', 'in', other_so.order_line.ids)
                    ])
                    regs.sudo().write({'sale_order_id': main_cart.id})

                    other_so._action_cancel()

                request.session['sale_order_id'] = main_cart.id
                request.session['seller_so_ids'] = pure_seller_orders.ids

            else:
                request.session['seller_so_ids'] = pure_seller_orders.ids

                standard_orders = pure_seller_orders.filtered(lambda o: not o.marketplace_seller_id)
                if standard_orders:
                    request.session['sale_order_id'] = standard_orders[0].id
                else:
                    request.session['sale_order_id'] = None

        return super().cart(access_token=access_token, revive=revive, **post)

class WebsiteSaleLoyalty(WebsiteSale):

    @http.route(['/shop/pricelist'],type='http', auth="public", website=True, sitemap=False,)
    def pricelist(self, promo, **post):
        redirect = post.get('r', '/shop/cart')

        pricelist_sudo = request.env['product.pricelist'].sudo().search(
            [('code', '=', promo)], limit=1
        )
        if pricelist_sudo and request.website.is_pricelist_available(pricelist_sudo.id):
            return super().pricelist(promo, **post)

        session_order_id = request.session.get('sale_order_id')
        master_agg_id = request.session.get('master_aggregator_so_id')

        if master_agg_id:
            order_sudo = request.env['sale.order'].sudo().browse(master_agg_id).exists()
            if not order_sudo or order_sudo.state != 'draft':
                order_sudo = request.website.sale_get_order(force_create=True)
        else:
            order_sudo = request.website.sale_get_order(force_create=True)

        if not order_sudo or not promo:
            return request.redirect("%s?code_not_available=1" % redirect)

        _logger.info(
            "pricelist: order=%s is_master=%s redirect=%s",
            order_sudo.name, order_sudo.is_combined_payment_order, redirect,
        )

        applied_codes = order_sudo.applied_coupon_ids.mapped('code')
        rule_codes = [getattr(r, 'code', '') for r in order_sudo.code_enabled_rule_ids if getattr(r, 'code', '')]
        all_codes = applied_codes + rule_codes

        if promo in all_codes:
            return request.redirect("%s?code_already_applied=1" % redirect)

        existing_reward_lines = order_sudo.order_line.filtered(lambda l: l.is_reward_line)
        if existing_reward_lines:
            _logger.warning("Blocking multiple codes: Reward lines already exist on %s", order_sudo.name)
            return request.redirect("%s?multiple_codes_not_allowed=1" % redirect)

        result = order_sudo._try_apply_code(promo)
        if not result or result.get('error') or result.get('not_found'):
            return request.redirect("%s?code_not_available=1" % redirect)

        # Normal (non-master) cart
        if not order_sudo.is_combined_payment_order:
            promo_upper = promo.upper()

            if 'LENOVO' in promo_upper:
                # ── LENOVO ──────────────────────────────────────────────
                _logger.info(
                    "pricelist: LENOVO – creating reward line directly on %s", order_sudo.name)
                self._create_lenovo_reward_line(order_sudo, promo)
                has_reward = order_sudo.order_line.filtered(lambda l: l.is_reward_line)
                if not has_reward:
                    _logger.info(
                        "pricelist: LENOVO not eligible – removing code from order %s", order_sudo.name)
                    lenovo_coupons = order_sudo.applied_coupon_ids.filtered(
                        lambda c: 'LENOVO' in (getattr(c, 'code', '') or '').upper()
                    )
                    lenovo_rules = order_sudo.code_enabled_rule_ids.filtered(
                        lambda r: 'LENOVO' in (getattr(r, 'code', '') or '').upper()
                    )
                    if lenovo_coupons:
                        order_sudo.sudo().write({
                            'applied_coupon_ids': [(3, c.id) for c in lenovo_coupons]
                        })
                    if lenovo_rules:
                        order_sudo.sudo().write({
                            'code_enabled_rule_ids': [(3, r.id) for r in lenovo_rules]
                        })
                    order_sudo.sudo().flush_recordset()
                    order_sudo.sudo().invalidate_recordset()
                    return request.redirect("%s?code_not_available=1" % redirect)

            elif 'ACCENTURE' in promo_upper:
                # ── ACCENTURE ──────────────────────────────────────────────
                _logger.info(
                    "pricelist: ACCENTURE – creating reward line directly on %s", order_sudo.name)
                self._create_accenture_reward_line(order_sudo, promo)
                has_reward = order_sudo.order_line.filtered(lambda l: l.is_reward_line)
                if not has_reward:
                    _logger.info(
                        "pricelist: ACCENTURE not eligible – removing code from order %s", order_sudo.name)
                    accenture_coupons = order_sudo.applied_coupon_ids.filtered(
                        lambda c: 'ACCENTURE' in (getattr(c, 'code', '') or '').upper()
                    )
                    accenture_rules = order_sudo.code_enabled_rule_ids.filtered(
                        lambda r: 'ACCENTURE' in (getattr(r, 'code', '') or '').upper()
                    )
                    if accenture_coupons:
                        order_sudo.sudo().write({
                            'applied_coupon_ids': [(3, c.id) for c in accenture_coupons]
                        })
                    if accenture_rules:
                        order_sudo.sudo().write({
                            'code_enabled_rule_ids': [(3, r.id) for r in accenture_rules]
                        })
                    order_sudo.sudo().flush_recordset()
                    order_sudo.sudo().invalidate_recordset()
                    return request.redirect("%s?code_not_available=1" % redirect)
            else:
                # ── Standard discount path ──────────────────────────────────
                self._create_standard_reward_line(order_sudo, promo)
                has_reward = order_sudo.order_line.filtered(lambda l: l.is_reward_line)
                if not has_reward:
                    # No eligible products → remove the applied code
                    _logger.info(
                        "pricelist: no eligible products – removing code %s from %s", promo, order_sudo.name)
                    order_sudo.sudo().write({
                        'applied_coupon_ids': [
                            (3, c.id) for c in order_sudo.applied_coupon_ids
                            if (getattr(c, 'code', '') or '').upper() == promo.upper()
                        ],
                        'code_enabled_rule_ids': [
                            (3, r.id) for r in order_sudo.code_enabled_rule_ids
                            if (getattr(r, 'code', '') or '').upper() == promo.upper()
                        ],
                    })
                    order_sudo.sudo().flush_recordset()
                    order_sudo.sudo().invalidate_recordset()
                    return request.redirect("%s?code_not_available=1" % redirect)

            order_sudo.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
            order_sudo.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
            return request.redirect(redirect)

        order_sudo = request.env['sale.order'].sudo().browse(order_sudo.id)
        reward_line_ids_after = set(order_sudo.order_line.filtered(lambda l: l.is_reward_line).ids)
        new_reward_lines = reward_line_ids_after

        if new_reward_lines:
            _logger.info(
                "pricelist FLOW-B: reward lines created immediately on master %s -> propagating",
                order_sudo.name)
            self._propagate_discount_to_seller_orders(order_sudo)
        else:
            _logger.info(
                "pricelist: no reward lines yet on master %s. Forcing update.",
                order_sudo.name)
            order_sudo._update_programs_and_rewards()

        return request.redirect(redirect)

    # ── LENOVO reward line builder ────────────────────────────────────────────
    def _create_lenovo_reward_line(self, order, promo='LENOVO'):
        """
        Create the reward line(s) for a LENOVO discount code.
        """
        regular_lines = order.order_line.filtered(lambda l: not l.is_reward_line)

        reward = None
        reward_product = None
        reward_label = 'LENOVO discount'
        identifier_code = 'LENOVO'

        for rule in order.code_enabled_rule_ids:
            program = getattr(rule, 'program_id', False)
            if not program:
                continue
            for r in program.reward_ids:
                if r.reward_type == 'discount' and r.discount:
                    if r.discount_line_product_id:
                        reward = r
                        reward_product = r.discount_line_product_id
                        reward_label = (
                            getattr(r, 'description', None)
                            or getattr(r, 'reward_description', None)
                            or 'LENOVO discount'
                        )
                        identifier_code = str(r.id)
                        break
            if reward:
                break

        # Fallback: check applied_coupon_ids
        if not reward:
            for coupon in order.applied_coupon_ids:
                program = getattr(coupon, 'program_id', False)
                if not program:
                    continue
                for r in program.reward_ids:
                    if r.reward_type == 'discount' and r.discount:
                        if r.discount_line_product_id:
                            reward = r
                            reward_product = r.discount_line_product_id
                            reward_label = (
                                getattr(r, 'description', None)
                                or getattr(r, 'reward_description', None)
                                or 'LENOVO discount'
                            )
                            identifier_code = str(r.id)
                            break
                if reward:
                    break

        if not reward or not reward_product:
            _logger.error(
                "_create_lenovo_reward_line: could not find reward/product for LENOVO on order %s.",
                order.name)
            return

        # Determine eligible lines (specific products or all)
        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products:
            eligible_lines = regular_lines.filtered(
                lambda l: l.product_id.id in target_products.ids
            )
        else:
            eligible_lines = regular_lines

        # LENOVO price-cap tiers
        LENOVO_CAPS = {
            269.0: 119.0,
            249.0:  99.0,
        }
        TOLERANCE = 0.50   # ±0.50 € float-comparison tolerance

        tax_groups = {}
        for sol in eligible_lines:
            if sol.product_uom_qty <= 0:
                continue

            tax_ids = sol.tax_id.ids if sol.tax_id else []
            if tax_ids:
                taxes = request.env['account.tax'].browse(tax_ids)
                tax_res = taxes.compute_all(1.0, currency=sol.order_id.currency_id)
                tax_factor = tax_res['total_included']
            else:
                tax_factor = 1.0

            price_excl = sol.price_unit
            price_incl = price_excl * tax_factor

            # Match against a LENOVO tier
            matched_cap_incl = None
            for original_incl, cap_incl in LENOVO_CAPS.items():
                if abs(price_incl - original_incl) <= TOLERANCE:
                    matched_cap_incl = cap_incl
                    break

            if matched_cap_incl is None:
                _logger.info(
                    "_create_lenovo_reward_line: product=%s price_incl=%.2f — "
                    "no matching LENOVO tier, skipping",
                    sol.product_id.name, price_incl,
                )
                continue

            cap_excl = matched_cap_incl / tax_factor if tax_factor else matched_cap_incl
            line_discount = -(price_excl - cap_excl) * sol.product_uom_qty

            if line_discount >= 0:
                continue

            key = frozenset(tax_ids)
            if key not in tax_groups:
                tax_groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
            tax_groups[key]['amount'] += line_discount

            _logger.info(
                "_create_lenovo_reward_line: product=%s qty=%s "
                "price_excl=%.4f price_incl=%.2f cap_incl=%.2f cap_excl=%.4f "
                "tax_factor=%.4f line_discount=%.4f tax_ids=%s",
                sol.product_id.name, sol.product_uom_qty,
                price_excl, price_incl, matched_cap_incl, cap_excl,
                tax_factor, line_discount, tax_ids,
            )

        if not tax_groups:
            _logger.warning(
                "_create_lenovo_reward_line: No eligible products for LENOVO on %s – "
                "reward line will NOT be created", order.name)
            return

        reward_label_with_code = f"{promo.upper()} discount"

        order._upsert_reward_lines(
            order, reward, reward_product, reward_label_with_code,
            identifier_code, tax_groups,
        )

        _logger.info(
            "_create_lenovo_reward_line: upserted tax-grouped reward lines on %s tax_groups=%s",
            order.name, {str(list(k)): v['amount'] for k, v in tax_groups.items()})

        order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
        order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

    def _create_accenture_reward_line(self, order, promo='ACCENTURE'):
        regular_lines = order.order_line.filtered(lambda l: not l.is_reward_line)

        reward = None
        reward_product = None
        reward_label = 'ACCENTURE discount'
        identifier_code = 'ACCENTURE'

        for rule in order.code_enabled_rule_ids:
            program = getattr(rule, 'program_id', False)
            if not program:
                continue
            for r in program.reward_ids:
                if r.reward_type == 'discount' and r.discount:
                    if r.discount_line_product_id:
                        reward = r
                        reward_product = r.discount_line_product_id
                        reward_label = (
                            getattr(r, 'description', None)
                            or getattr(r, 'reward_description', None)
                            or 'ACCENTURE discount'
                        )
                        identifier_code = str(r.id)
                        break
            if reward:
                break

        # Also check applied_coupon_ids programs as fallback
        if not reward:
            for coupon in order.applied_coupon_ids:
                program = getattr(coupon, 'program_id', False)
                if not program:
                    continue
                for r in program.reward_ids:
                    if r.reward_type == 'discount' and r.discount:
                        if r.discount_line_product_id:
                            reward = r
                            reward_product = r.discount_line_product_id
                            reward_label = (
                                getattr(r, 'description', None)
                                or getattr(r, 'reward_description', None)
                                or 'ACCENTURE discount'
                            )
                            identifier_code = str(r.id)
                            break
                if reward:
                    break

        if not reward or not reward_product:
            _logger.error(
                "_create_accenture_reward_line: could not find reward/product for ACCENTURE on order %s.",
                order.name)
            return

        # Determine eligible lines (specific products or all)
        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products:
            eligible_lines = regular_lines.filtered(
                lambda l: l.product_id.id in target_products.ids
            )
        else:
            eligible_lines = regular_lines

        # ACCENTURE price cap
        ACCENTURE_PRICES = {
            'ACCENTURE2': 189.0,
            'ACCENTURE':  64.0,
        }
        promo_key = promo.upper()
        cap_price = next(
            (price for key, price in sorted(ACCENTURE_PRICES.items(), key=lambda x: -len(x[0])) if key in promo_key),
            64.0,
        )
        _logger.info('_create_accenture_reward_line: promo=%s cap_price=%s', promo, cap_price)

        # Per-line traversal grouped by tax
        tax_groups = {}
        for sol in eligible_lines:
            if sol.product_uom_qty <= 0:
                continue
            original = sol.price_unit
            tax_ids = sol.tax_id.ids if sol.tax_id else []
            if tax_ids:
                taxes = request.env['account.tax'].browse(tax_ids)
                tax_res = taxes.compute_all(1.0, currency=sol.order_id.currency_id)
                tax_factor = tax_res['total_included']  # e.g. 1.23 for 23%
            else:
                tax_factor = 1.0
            cap_excl_tax = cap_price / tax_factor if tax_factor else cap_price
            if original <= cap_excl_tax:
                continue
            line_discount = -max(0.0, (original - cap_excl_tax) * sol.product_uom_qty)
            key = frozenset(tax_ids)
            if key not in tax_groups:
                tax_groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
            tax_groups[key]['amount'] += line_discount
            _logger.info(
                "_create_accenture_reward_line: product=%s qty=%s original=%s "
                "cap_price(incl)=%s cap_excl_tax=%s tax_factor=%s → line_discount=%s tax_ids=%s",
                sol.product_id.name, sol.product_uom_qty, original,
                cap_price, cap_excl_tax, tax_factor, line_discount, tax_ids,
            )

        if not tax_groups:
            _logger.warning(
                "_create_accenture_reward_line: No eligible products for ACCENTURE on %s – "
                "reward line will NOT be created", order.name)
            return

        # Store the promo code in the reward line name so _get_accenture_price can detect it later
        reward_label_with_code = f"{promo.upper()} discount"

        order._upsert_reward_lines(
            order, reward, reward_product, reward_label_with_code,
            identifier_code, tax_groups,
        )

        _logger.info(
            "_create_accenture_reward_line: upserted tax-grouped reward lines on %s tax_groups=%s",
            order.name, {str(list(k)): v['amount'] for k, v in tax_groups.items()})

        order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
        order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

    def _create_standard_reward_line(self, order, promo):
        """
        Create/update the reward line(s) for a standard (non-ACCENTURE, non-LENOVO) discount code,
        one line per tax group, so taxes are correctly applied to the discounted amount.
        """
        regular_lines = order.order_line.filtered(lambda l: not l.is_reward_line)

        # Find the reward from applied codes
        reward = None
        reward_product = None
        reward_label = promo
        identifier_code = promo

        for rule in order.code_enabled_rule_ids:
            program = getattr(rule, 'program_id', False)
            if not program:
                continue
            for r in program.reward_ids:
                if r.reward_type == 'discount' and r.discount and r.discount_line_product_id:
                    reward = r
                    reward_product = r.discount_line_product_id
                    reward_label = (
                        getattr(r, 'description', None)
                        or getattr(r, 'reward_description', None)
                        or promo
                    )
                    identifier_code = str(r.id)
                    break
            if reward:
                break

        if not reward:
            for coupon in order.applied_coupon_ids:
                program = getattr(coupon, 'program_id', False)
                if not program:
                    continue
                for r in program.reward_ids:
                    if r.reward_type == 'discount' and r.discount and r.discount_line_product_id:
                        reward = r
                        reward_product = r.discount_line_product_id
                        reward_label = (
                            getattr(r, 'description', None)
                            or getattr(r, 'reward_description', None)
                            or promo
                        )
                        identifier_code = str(r.id)
                        break
                if reward:
                    break

        if not reward or not reward_product:
            _logger.error(
                "_create_standard_reward_line: could not find reward/product for promo=%s on %s",
                promo, order.name)
            return

        # Per-line, tax-aware grouping
        tax_groups = order._group_discounts_by_tax(regular_lines, reward, None)

        _logger.info(
            "_create_standard_reward_line: order=%s promo=%s tax_groups=%s",
            order.name, promo,
            {str(list(k)): v['amount'] for k, v in tax_groups.items()},
        )

        if not tax_groups:
            _logger.warning(
                "_create_standard_reward_line: no eligible products for %s on %s", promo, order.name)
            return

        order._upsert_reward_lines(
            order, reward, reward_product, reward_label,
            identifier_code, tax_groups,
        )

    @http.route(['/shop/claimreward'], type='http', auth="public", website=True, sitemap=False)
    def claim_reward(self, *args, **post):
        redirect = post.get('r', '/shop/checkout')
        master_agg_id = request.session.get('master_aggregator_so_id')

        if master_agg_id:
            order_sudo = request.env['sale.order'].sudo().browse(master_agg_id).exists()
            if not order_sudo or order_sudo.state != 'draft':
                order_sudo = request.website.sale_get_order(force_create=True)
        else:
            order_sudo = request.website.sale_get_order(force_create=True)

        is_master = bool(order_sudo and order_sudo.is_combined_payment_order)

        _logger.info(
            "claim_reward: order=%s is_master=%s",
            order_sudo.name if order_sudo else 'None',
            is_master,
        )

        if order_sudo and order_sudo.order_line.filtered(lambda l: l.is_reward_line):
           _logger.warning("Blocking multiple rewards in claim_reward")
           return request.redirect("%s?multiple_codes_not_allowed=1" % redirect)

        # Let Odoo create the reward line
        response = super().claim_reward(*args, **post)

        # Now propagate to seller orders if this is the master
        if is_master and order_sudo:
            order_sudo = request.env['sale.order'].sudo().browse(order_sudo.id)
            _logger.info(
                "claim_reward: propagating discount after reward line creation on %s",
                order_sudo.name,
            )
            self._propagate_discount_to_seller_orders(order_sudo)

        return response

    #  _propagate_discount_to_seller_orders  (per-line, tax-aware)        #
    def _propagate_discount_to_seller_orders(self, master_order):
        linked_orders = master_order.linked_seller_order_ids
        if not linked_orders:
            _logger.warning(
                "_propagate: No linked seller orders on %s", master_order.name
            )
            return

        _logger.info(
            "_propagate: master=%s sellers=%s",
            master_order.name, linked_orders.mapped('name'),
        )

        master_reward_lines = master_order.order_line.filtered(
            lambda l: l.is_reward_line and l.reward_id
        )

        # Collect unique rewards (there may be multiple reward lines per reward when tax-grouped)
        seen_reward_ids = set()
        rewards_to_process = []
        for rl in master_reward_lines:
            if rl.reward_id.id not in seen_reward_ids:
                seen_reward_ids.add(rl.reward_id.id)
                rewards_to_process.append(rl.reward_id)

        _logger.info("_propagate: unique rewards to process: %s", [r.id for r in rewards_to_process])

        for reward in rewards_to_process:
            reward_label = (
                getattr(reward, 'description', None)
                or getattr(reward, 'reward_description', None)
                or str(reward.id)
            )
            if reward.reward_type != 'discount' or not reward.discount:
                _logger.info("_propagate: skipping non-discount reward %s", reward_label)
                continue

            reward_product = reward.discount_line_product_id
            if not reward_product:
                _logger.warning("_propagate: reward %s has no discount_line_product_id", reward_label)
                continue

            # Get one of the master reward lines for this reward (for identifier_code)
            sample_master_rl = master_reward_lines.filtered(
                lambda l: l.reward_id.id == reward.id
            )[:1]

            for so in linked_orders:
                so.sudo().write({
                    'applied_coupon_ids': [(4, c) for c in master_order.applied_coupon_ids.ids],
                    'code_enabled_rule_ids': [(4, r) for r in master_order.code_enabled_rule_ids.ids],
                })

            master_tax_groups = {}
            total_master_discount = 0.0

            # Per seller order → per sale order line traversal
            for so in linked_orders:
                so_regular = so.order_line.filtered(lambda l: not l.is_reward_line)
                tax_groups = master_order._group_discounts_by_tax(so_regular, reward, sample_master_rl or None)

                if not tax_groups:
                    _logger.info("_propagate: %s has no discount → skip", so.name)
                    continue

                seller_total = sum(g['amount'] for g in tax_groups.values())
                total_master_discount += seller_total

                _logger.info(
                    "_propagate: so=%s tax_groups=%s seller_total=%s",
                    so.name,
                    {str(list(k)): v['amount'] for k, v in tax_groups.items()},
                    seller_total,
                )

                so._upsert_reward_lines(
                    so, reward, reward_product,
                    sample_master_rl.name if sample_master_rl else reward_label,
                    sample_master_rl.reward_identifier_code if sample_master_rl else str(reward.id),
                    tax_groups, sample_master_rl or None,
                )

                for key, group in tax_groups.items():
                    if key not in master_tax_groups:
                        master_tax_groups[key] = {'amount': 0.0, 'tax_ids': group['tax_ids']}
                    master_tax_groups[key]['amount'] += group['amount']

                so.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
                so.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

            if master_tax_groups and total_master_discount != 0.0:
                _logger.info(
                    "_propagate: updating master reward lines for reward=%s tax_groups=%s total=%s",
                    reward.id,
                    {str(list(k)): v['amount'] for k, v in master_tax_groups.items()},
                    total_master_discount,
                )
                # becomes a ghost record and field access raises MissingError.
                rl_name = (sample_master_rl.name if sample_master_rl else reward_label)
                rl_identifier = (
                    sample_master_rl.reward_identifier_code
                    if sample_master_rl else str(reward.id)
                )

                old_master_lines = master_order.order_line.filtered(
                    lambda l: l.is_reward_line and l.reward_id and l.reward_id.id == reward.id
                ).exists()
                if old_master_lines:
                    old_master_lines.sudo().unlink()

                master_order._upsert_reward_lines(
                    master_order, reward, reward_product,
                    rl_name, rl_identifier,
                    master_tax_groups,
                )

            master_order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
            master_order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])