from odoo import models, fields, api, _
from odoo.http import request
import logging
import base64
from datetime import datetime, time
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_combined_payment_order = fields.Boolean("Is Combined Payment Order", default=False)
    linked_seller_order_ids = fields.Many2many(
        'sale.order',
        'sale_order_combined_rel',
        'master_id',
        'seller_id',
        string="Linked Seller Orders"
    )
    unpaid_reminder_sent = fields.Boolean("Unpaid Reminder Sent", default=False)

    # ── LENOVO price-cap table ──────────────────────────────────────────────
    LENOVO_PRICE_CAPS = {
        269.0: 119.0,
        249.0:  99.0,
    }

    def _get_lenovo_caps(self):
        """Return the LENOVO price-cap mapping {original_incl -> cap_incl}."""
        return self.LENOVO_PRICE_CAPS

    def _is_lenovo_discount(self, reward, line=None):
        """
        Return True if the promo code on this order / reward / line is LENOVO.
        """
        check_strs = []

        if line:
            line_name = str(getattr(line, 'name', ''))
            if line_name:
                check_strs.insert(0, line_name)
            reward_id_code = str(getattr(line, 'reward_identifier_code', ''))
            if reward_id_code:
                check_strs.append(reward_id_code)
            if hasattr(line, 'coupon_id') and getattr(line.coupon_id, 'code', False):
                check_strs.append(str(line.coupon_id.code))

        if reward:
            check_strs.extend([
                str(getattr(reward, 'description', '')),
                str(getattr(reward, 'name', '')),
            ])
            if hasattr(reward, 'program_id') and getattr(reward.program_id, 'name', False):
                check_strs.append(str(reward.program_id.name))
            if hasattr(reward, 'program_id'):
                program = reward.program_id
                if hasattr(program, 'rule_ids'):
                    for rule in program.rule_ids:
                        if getattr(rule, 'code', False):
                            check_strs.append(str(rule.code))

        for rule in self.code_enabled_rule_ids:
            code = getattr(rule, 'code', False)
            if code:
                check_strs.append(str(code))
        for coupon in self.applied_coupon_ids:
            code = getattr(coupon, 'code', False)
            if code:
                check_strs.append(str(code))

        check_strs = [s.upper() for s in check_strs if s]
        return any('LENOVO' in s for s in check_strs)

    def _get_accenture_price(self, reward, line=None):
        self.ensure_one()
        check_strs = []

        if line:
            line_name = str(getattr(line, 'name', ''))
            if line_name:
                check_strs.insert(0, line_name)

            reward_id_code = str(getattr(line, 'reward_identifier_code', ''))
            if reward_id_code:
                check_strs.append(reward_id_code)

            if hasattr(line, 'coupon_id') and getattr(line.coupon_id, 'code', False):
                check_strs.append(str(line.coupon_id.code))

        if reward:
            check_strs.extend([
                str(getattr(reward, 'description', '')),
                str(getattr(reward, 'name', '')),
            ])
            if hasattr(reward, 'program_id') and getattr(reward.program_id, 'name', False):
                check_strs.append(str(reward.program_id.name))
            # Check if the reward's program has ACCENTURE rules
            if hasattr(reward, 'program_id'):
                program = reward.program_id
                if hasattr(program, 'rule_ids'):
                    for rule in program.rule_ids:
                        if getattr(rule, 'code', False):
                            check_strs.append(str(rule.code))

        # Also check the order's applied codes directly — most reliable source
        for rule in self.code_enabled_rule_ids:
            code = getattr(rule, 'code', False)
            if code:
                check_strs.append(str(code))
        for coupon in self.applied_coupon_ids:
            code = getattr(coupon, 'code', False)
            if code:
                check_strs.append(str(code))

        check_strs = [s.upper() for s in check_strs if s]

        # Scan ALL strings for ACCENTURE2 first before checking ACCENTURE.
        has_accenture2 = any('ACCENTURE2' in s for s in check_strs)
        has_accenture = any('ACCENTURE' in s for s in check_strs)

        if has_accenture2:
            return 189.0
        elif has_accenture:
            return 64.0

        return None

    def _is_accenture_discount(self, reward, line=None):
        return self._get_accenture_price(reward, line) is not None

    def _get_tax_factor(self, tax_ids):
        """
        Given a list of tax IDs, compute the combined tax-inclusive factor.
        e.g. for 23% VAT returns 1.23
        """
        if not tax_ids:
            return 1.0
        taxes = self.env['account.tax'].browse(tax_ids)
        tax_res = taxes.compute_all(1.0, currency=self.currency_id)
        return tax_res['total_included']  # e.g. 1.23 for 23% VAT

    #  CORE HELPER: group line discounts by tax fingerprint
    def _group_discounts_by_tax(self, regular_lines, reward, reward_line=None):
        """
        Compute discount amounts grouped by tax fingerprint.
        """
        # LENOVO
        if self._is_lenovo_discount(reward, reward_line):
            return self._group_discounts_lenovo(regular_lines, reward, reward_line)

        # ACCENTURE
        is_accenture = self._is_accenture_discount(reward, reward_line)
        if is_accenture:
            return self._group_discounts_accenture(regular_lines, reward, reward_line)

        # ── Determine eligible lines ─────────────────────────────────────────
        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products:
            target_product_ids = set(target_products.ids)
            target_tmpl_ids = set(target_products.mapped('product_tmpl_id').ids)
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
                          and (
                              l.product_id.id in target_product_ids
                              or (l.product_id.product_tmpl_id
                                  and l.product_id.product_tmpl_id.id in target_tmpl_ids)
                          )
            )
        else:
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
            )

        if not eligible_lines:
            return {}

        discount_mode = getattr(reward, 'discount_mode', '')

        # ── PERCENT discount ─────────────────────────────────────────────────
        if discount_mode == 'percent':
            groups = {}
            for sol in eligible_lines:
                tax_ids = sol.tax_id.ids if sol.tax_id else []
                eligible_amount = sol.price_unit * sol.product_uom_qty
                amount = -abs(eligible_amount * (reward.discount / 100.0))
                if amount == 0.0:
                    continue
                key = frozenset(tax_ids)
                if key not in groups:
                    groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
                groups[key]['amount'] += amount
                _logger.info(
                    "_group_discounts_by_tax PERCENT: product=%s qty=%s amount=%s tax_ids=%s",
                    sol.product_id.name, sol.product_uom_qty, amount, tax_ids,
                )
            return groups

        # ── FIXED / PER_ORDER discount ───────────────────────────────────────
        groups = {}
        for sol in eligible_lines:
            tax_ids = sol.tax_id.ids if sol.tax_id else []
            tax_factor = self._get_tax_factor(tax_ids)
            # Full reward.discount applied per unit, multiplied by qty
            line_excl = (reward.discount / tax_factor if tax_factor else reward.discount) * sol.product_uom_qty
            amount = -abs(line_excl)
            if amount == 0.0:
                continue
            key = frozenset(tax_ids)
            if key not in groups:
                groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
            groups[key]['amount'] += amount
            _logger.info(
                "_group_discounts_by_tax FIXED: product=%s qty=%s tax_ids=%s "
                "tax_factor=%s reward.discount=%s line_excl=%s running_group_total=%s",
                sol.product_id.name, sol.product_uom_qty, tax_ids,
                tax_factor, reward.discount, line_excl, groups[key]['amount'],
            )

        return groups

    def _group_discounts_lenovo(self, regular_lines, reward, reward_line=None):
        TOLERANCE = 0.50
        caps = self._get_lenovo_caps()

        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products:
            target_product_ids = set(target_products.ids)
            target_tmpl_ids = set(target_products.mapped('product_tmpl_id').ids)
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
                          and (
                              l.product_id.id in target_product_ids
                              or (l.product_id.product_tmpl_id
                                  and l.product_id.product_tmpl_id.id in target_tmpl_ids)
                          )
            )
        else:
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
            )

        groups = {}
        for sol in eligible_lines:
            tax_ids = sol.tax_id.ids if sol.tax_id else []
            tax_factor = self._get_tax_factor(tax_ids)
            price_excl = sol.price_unit
            price_incl = price_excl * tax_factor   # tax-inclusive price for this line

            # Find a matching LENOVO tier (within tolerance)
            matched_cap_incl = None
            for original_incl, cap_incl in caps.items():
                if abs(price_incl - original_incl) <= TOLERANCE:
                    matched_cap_incl = cap_incl
                    break

            if matched_cap_incl is None:
                _logger.info(
                    "_group_discounts_lenovo: product=%s price_incl=%.2f — "
                    "no matching LENOVO tier, skipping",
                    sol.product_id.name, price_incl,
                )
                continue

            # Convert the cap back to tax-exclusive for the reward line price_unit
            cap_excl = matched_cap_incl / tax_factor if tax_factor else matched_cap_incl
            line_discount = -(price_excl - cap_excl) * sol.product_uom_qty

            if line_discount >= 0:
                # price is already at or below cap — nothing to discount
                continue

            key = frozenset(tax_ids)
            if key not in groups:
                groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
            groups[key]['amount'] += line_discount

            _logger.info(
                "_group_discounts_lenovo: product=%s qty=%s "
                "price_excl=%.4f price_incl=%.2f matched_original=%.2f "
                "cap_incl=%.2f cap_excl=%.4f tax_factor=%.4f "
                "line_discount=%.4f tax_ids=%s",
                sol.product_id.name, sol.product_uom_qty,
                price_excl, price_incl,
                next(o for o, c in caps.items() if abs(price_incl - o) <= TOLERANCE),
                matched_cap_incl, cap_excl, tax_factor,
                line_discount, tax_ids,
            )

        return groups

    def _group_discounts_accenture(self, regular_lines, reward, reward_line=None):
        """
        ACCENTURE-specific discount grouping.
        Cap each eligible product's price to the ACCENTURE cap price (tax-inclusive).
        """
        acc_price = self._get_accenture_price(reward, reward_line)
        if acc_price is None:
            return {}

        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products:
            target_product_ids = set(target_products.ids)
            target_tmpl_ids = set(target_products.mapped('product_tmpl_id').ids)
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
                          and (
                              l.product_id.id in target_product_ids
                              or (l.product_id.product_tmpl_id
                                  and l.product_id.product_tmpl_id.id in target_tmpl_ids)
                          )
            )
        else:
            eligible_lines = regular_lines.filtered(
                lambda l: not l.is_reward_line and l.product_uom_qty > 0
            )

        groups = {}
        for sol in eligible_lines:
            tax_ids = sol.tax_id.ids if sol.tax_id else []
            tax_factor = self._get_tax_factor(tax_ids)
            original = sol.price_unit
            cap_excl_tax = acc_price / tax_factor if tax_factor else acc_price
            if original <= cap_excl_tax:
                continue
            line_discount = -max(0.0, (original - cap_excl_tax) * sol.product_uom_qty)
            key = frozenset(tax_ids)
            if key not in groups:
                groups[key] = {'amount': 0.0, 'tax_ids': tax_ids}
            groups[key]['amount'] += line_discount
            _logger.info(
                "_group_discounts_accenture: product=%s qty=%s original=%s "
                "cap_price(incl)=%s cap_excl_tax=%s tax_factor=%s line_discount=%s tax_ids=%s",
                sol.product_id.name, sol.product_uom_qty, original,
                acc_price, cap_excl_tax, tax_factor, line_discount, tax_ids,
            )
        return groups

    def _compute_line_discount(self, sol, reward, reward_line=None):
        """
        Returns (discount_amount, tax_ids) for a SINGLE sale order line.
        NOTE: For fixed-amount discounts with multiple eligible lines use
        _group_discounts_by_tax instead, which distributes proportionally.
        """
        if sol.is_reward_line:
            return 0.0, []

        target_products = (
            getattr(reward, 'discount_specific_product_ids', False)
            or getattr(reward, 'discount_product_ids', False)
        )
        if target_products and sol.product_id.id not in target_products.ids:
            return 0.0, []

        qty = sol.product_uom_qty
        if qty <= 0:
            return 0.0, []

        # Collect the tax IDs from the product line
        tax_ids = sol.tax_id.ids if sol.tax_id else []

        # LENOVO
        if self._is_lenovo_discount(reward, reward_line):
            caps = self._get_lenovo_caps()
            TOLERANCE = 0.50
            tax_factor = self._get_tax_factor(tax_ids)
            price_incl = sol.price_unit * tax_factor
            matched_cap_incl = None
            for original_incl, cap_incl in caps.items():
                if abs(price_incl - original_incl) <= TOLERANCE:
                    matched_cap_incl = cap_incl
                    break
            if matched_cap_incl is None:
                return 0.0, []
            cap_excl = matched_cap_incl / tax_factor if tax_factor else matched_cap_incl
            discount = -(sol.price_unit - cap_excl) * qty
            return (discount if discount < 0 else 0.0), tax_ids

        is_accenture = self._is_accenture_discount(reward, reward_line)

        if is_accenture:
            acc_price = self._get_accenture_price(reward, reward_line)
            if acc_price is None:
                return 0.0, []
            original = sol.price_unit
            tax_factor = self._get_tax_factor(tax_ids)
            cap_excl_tax = acc_price / tax_factor if tax_factor else acc_price
            if original <= cap_excl_tax:
                return 0.0, []
            return -max(0.0, (original - cap_excl_tax) * qty), tax_ids

        discount_mode = getattr(reward, 'discount_mode', '')

        if discount_mode == 'percent':
            eligible_amount = sol.price_unit * qty
            return -abs(eligible_amount * (reward.discount / 100.0)), tax_ids
        else:
            # Fixed: treat reward.discount as tax-inclusive total for this single line
            tax_factor = self._get_tax_factor(tax_ids)
            share_excl = reward.discount / tax_factor if tax_factor else reward.discount
            return -abs(share_excl), tax_ids

    #  HELPER: upsert reward lines for a given order (one per tax group)
    def _upsert_reward_lines(self, order, reward, reward_product, reward_label,
                             identifier_code, tax_groups, master_reward_line=None):
        """
        Create or update reward lines on `order`, one per tax group.
        Removes stale reward lines for this reward that are no longer needed.

        tax_groups: dict from _group_discounts_by_tax
        Returns the total discount amount written to this order.
        """
        if not tax_groups:
            # No discount at all — remove existing reward lines
            existing = order.order_line.filtered(
                lambda l: l.is_reward_line and l.reward_id and l.reward_id.id == reward.id
            )
            if existing:
                existing.sudo().unlink()
            return 0.0

        total = sum(g['amount'] for g in tax_groups.values())

        # Build the set of tax fingerprints we need
        needed_keys = set(tax_groups.keys())

        # Find existing reward lines for this reward on this order
        existing_lines = order.order_line.filtered(
            lambda l: l.is_reward_line and l.reward_id and l.reward_id.id == reward.id
        )

        # Map existing lines by their current tax fingerprint
        existing_by_key = {}
        for el in existing_lines:
            key = frozenset(el.tax_id.ids)
            existing_by_key[key] = el

        # Update / create
        for key, group in tax_groups.items():
            amount = group['amount']
            tax_ids = group['tax_ids']
            if key in existing_by_key:
                existing_by_key[key].sudo().write({
                    'price_unit': amount,
                    'tax_id': [(6, 0, tax_ids)],
                })
                del existing_by_key[key]
            else:
                ref_line = master_reward_line
                self.env['sale.order.line'].sudo().create({
                    'order_id': order.id,
                    'product_id': reward_product.id,
                    'name': reward_label,
                    'product_uom_qty': 1,
                    'price_unit': amount,
                    'tax_id': [(6, 0, tax_ids)],
                    'is_reward_line': True,
                    'reward_id': reward.id,
                    'reward_identifier_code': (
                        ref_line.reward_identifier_code if ref_line else identifier_code
                    ),
                })

        # Remove stale lines (tax groups that no longer exist)
        for stale_line in existing_by_key.values():
            stale_line.sudo().unlink()

        return total

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.marketplace_seller_id:
            invoice_vals['marketplace_seller_id'] = self.marketplace_seller_id.id
        return invoice_vals


    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        res = super(SaleOrder, self)._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

        if self.env.context.get('auto_adding_membership'):
            return res

        add_qty = int(add_qty or 0)
        set_qty = int(set_qty or 0)
        if add_qty > 0 or set_qty > 0:
            try:
                product = self.env['product.product'].browse(product_id)

                if product.type == 'service' and product.marketplace_seller_id:
                    seller_id = product.marketplace_seller_id.id

                    config = self.env['seller.membership.config'].sudo().search([
                        ('seller_id', '=', seller_id)
                    ], limit=1)

                    if config and config.product_id:
                        membership_product = config.product_id
                        partner = self.partner_id

                        existing_sub = self.env['sale.order'].sudo().search([
                            ('partner_id', '=', partner.id),
                            ('state', 'in', ['sale', 'done']),
                            ('order_line.product_id', '=', membership_product.id)
                        ], limit=1)

                        if not existing_sub:
                            existing_line = self.order_line.filtered(
                                lambda l: l.product_id.id == membership_product.id
                            )

                            if not existing_line:
                                _logger.info(f"Auto-adding Membership {membership_product.name}")

                                self.with_context(auto_adding_membership=True)._cart_update(
                                    product_id=membership_product.id,
                                    add_qty=1
                                )

                                # Set Plan via Pricing
                                if membership_product.recurring_invoice:
                                    pricings = membership_product.sudo().product_subscription_pricing_ids
                                    if pricings:
                                        plan = pricings[0].plan_id
                                        if plan:
                                            self.sudo().write({'plan_id': plan.id})
                                            _logger.info(f"Set Plan ID {plan.name} on Order {self.name}")

            except Exception as e:
                _logger.error(f"Error in auto-add membership logic: {str(e)}")
        is_reduction = (set_qty == 0 and add_qty <= 0) or (add_qty < 0)
        if is_reduction:
            try:
                product = self.env['product.product'].browse(product_id)
                # Only check for auto-removal if we are removing an event
                if not product.recurring_invoice and product.marketplace_seller_id.name == 'Táborčatá, o. z.':
                    membership_line = self.order_line.filtered(lambda l: l.product_id.recurring_invoice)
    
                    if membership_line:
                        remaining_taborcata_events = self.order_line.filtered(
                            lambda l: not l.product_id.recurring_invoice and
                                      l.product_id.marketplace_seller_id.name == 'Táborčatá, o. z.'
                        )
    
                        if not remaining_taborcata_events:
                            _logger.info(
                                f"Removing Membership {membership_line.product_id.name} from Order {self.name} - no related events left.")
    
                            membership_line.sudo().unlink()
                            self.sudo().write({'plan_id': False})

            except Exception as e:
                _logger.error(f"Error in auto-remove membership logic: {str(e)}")
        return res


    def _process_combined_payment(self, tx):
        self.ensure_one()

        master_orders = tx.sale_order_ids.filtered('is_combined_payment_order')

        # Handle Single Orders
        normal_orders = tx.sale_order_ids.filtered(lambda o: not o.is_combined_payment_order and o.website_id)
        if normal_orders:
            for so in normal_orders:
                try:
                    if not so.marketplace_seller_id:
                        for line in so.order_line:
                            if line.product_id.marketplace_seller_id:
                                so.sudo().write({'marketplace_seller_id': line.product_id.marketplace_seller_id.id})
                                break
                    if so.state in ['draft', 'sent']:
                        so.action_confirm()
                    # Deferred until payment is complete
                    # self._auto_invoice_and_reconcile(so, tx.payment_id,tx=tx)
                    self._send_custom_mails(so)
                except Exception as e:
                    _logger.error(f"Error processing single order {so.name}: {str(e)}")

        if not master_orders:
            return

        payment = tx.payment_id

        for master_so in master_orders:
            for seller_so in master_so.linked_seller_order_ids:
                try:
                    # link the Payment Transaction to the Split Order
                    # This tells Odoo "This Seller Order is paid by Transaction X"
                    tx.write({'sale_order_ids': [(4, seller_so.id)]})

                    if seller_so.partner_id != master_so.partner_id:
                        seller_so.sudo().write({
                            'partner_id': master_so.partner_id.id,
                            'partner_invoice_id': master_so.partner_invoice_id.id,
                            'partner_shipping_id': master_so.partner_shipping_id.id,
                        })

                    # Auto assign seller
                    if not seller_so.marketplace_seller_id:
                        for line in seller_so.order_line:
                            if line.product_id.marketplace_seller_id:
                                seller_so.sudo().write({
                                    'marketplace_seller_id':
                                        line.product_id.marketplace_seller_id.id
                                })
                                break

                    # Confirm order
                    if seller_so.state in ('draft', 'sent'):
                        seller_so.action_confirm()

                    # 2. Invoice & Reconcile
                    # Deferred until payment is complete
                    # self._auto_invoice_and_reconcile(seller_so, payment)

                    # 3. Send Mails
                    self._send_custom_mails(seller_so)

                except Exception as e:
                    _logger.exception("Error processing seller order %s", seller_so.name)

            # Cancel Master Order Safely
            try:
                for inv in master_so.invoice_ids:
                    if inv.state == 'posted':
                        inv.button_draft()
                    if inv.state != 'cancel':
                        inv.button_cancel()
                master_so._action_cancel()
            except Exception as e:
                _logger.error(f"Error cancelling Master Order {master_so.name}: {str(e)}")

    def _send_custom_mails(self, order):
        registrations = self.env['event.registration'].sudo().search([
            ('sale_order_id', '=', order.id),
            ('state', 'in', ['open', 'done'])
        ])

        for reg in registrations:
            recipient_email = reg.email or reg.partner_id.email
            if not recipient_email:
                continue

            attachment_ids = []
            try:
                pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                    'event.action_report_event_registration_full_page_ticket', res_ids=reg.id)
                ticket_attach = self.env['ir.attachment'].sudo().create({
                    'name': f"Ticket_{reg.name}.pdf",
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'event.registration',
                    'res_id': reg.id,
                    'mimetype': 'application/pdf',
                })
                attachment_ids.append(ticket_attach.id)
            except Exception:
                pass

            mail_schedulers = reg.event_id.event_mail_ids.filtered(
                lambda m: m.interval_unit == 'now' and m.notification_type == 'mail'
            )

            for scheduler in mail_schedulers:
                if scheduler.template_ref:
                    scheduler.template_ref.send_mail(
                        reg.id,
                        force_send=True,
                        email_values={
                            'email_from': 'taborcata@taborcata.sk',
                            'email_to': recipient_email,
                            'attachment_ids': [(4, aid) for aid in attachment_ids]
                        }
                    )

        template = self.env.ref('multi_payment_checkout.taborcata_sale_confirmation', raise_if_not_found=False)
        if template:
            # Use send_mail instead of message_post_with_source to actually send the email out
            template.send_mail(order.id, force_send=True,email_values={'email_from': 'taborcata@taborcata.sk'})
            _logger.info(f"Sent Custom Slovak Mail for {order.name}")
        else:
            _logger.warning("Custom sale template 'taborcata_sale_confirmation' not found.")

    def _auto_invoice_and_reconcile(self, sale_order, payment,tx=None):
        invoices = sale_order._create_invoices()
        if not tx:
            if payment:
                tx = payment.payment_transaction_id
            if not tx:
                tx = sale_order.transaction_ids.sudo().sorted('id', reverse=True)[:1]

        is_bank_transfer = False
        if tx:
            # 1. Check Provider
            if tx.provider_code in ['wire_transfer', 'transfer']:
                is_bank_transfer = True

            if tx.payment_method_id and tx.payment_method_id.code in ['bank_transfer', 'wire_transfer']:
                is_bank_transfer = True

            _logger.info(
                f"Order {sale_order.name} | TX: {tx.reference} | Provider: {tx.provider_code} | Method: {tx.payment_method_id.code if tx.payment_method_id else 'None'} -> IS BANK TRANSFER? {is_bank_transfer}")
        else:
            _logger.warning(f"Order {sale_order.name} | NO TRANSACTION FOUND. Assuming Not Bank Transfer.")

        for inv in invoices:
            if inv.state == 'draft':
                inv.write({
                    'delivery_date': fields.Date.context_today(self),
                    'show_delivery_date': True,
                })
                inv.action_post()

            if not is_bank_transfer:
                try:
                    template = self.env.ref('multi_payment_checkout.taborcata_invoice_confirmation',raise_if_not_found=False)
                    if template:
                        pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                            'account.account_invoices', res_ids=inv.id)
                        attachment = self.env['ir.attachment'].sudo().create({
                            'name': f"{inv.name}.pdf".replace('/', '_'),
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_content),
                            'res_model': 'account.move',
                            'res_id': inv.id,
                            'mimetype': 'application/pdf',
                        })

                        # Use send_mail with email_values to attach the PDF
                        template.send_mail(inv.id,
                                           force_send = True,
                                           email_values = {'attachment_ids': [(4, attachment.id)],'email_from': 'taborcata@taborcata.sk'})
                        _logger.info(f"Invoice Mail with PDF sent for: {inv.name}")
                except Exception:
                    _logger.exception(
                        "Failed to send invoice email for %s", inv.name
                    )
            else:
                _logger.info(f"Skipping Invoice Email for {inv.name} because payment is Bank Transfer")

            if not payment:
                tx = sale_order.get_portal_last_transaction()
                if tx and tx.payment_id:
                    payment = tx.payment_id

            if payment and payment.move_id:
                # Find the credit line (money we received)
                receivable_line = payment.move_id.line_ids.filtered(
                    lambda l: l.account_type == 'asset_receivable' and not l.reconciled
                )
                if receivable_line:
                    try:
                        # This works exactly like the "100-50" logic you described.
                        # It applies a partial reconcile if the invoice amount < payment amount.
                        inv.js_assign_outstanding_line(receivable_line.id)
                        _logger.info(f"Successfully reconciled invoice {inv.name}")
                    except Exception as e:
                        _logger.warning(f"Could not auto-reconcile invoice {inv.name}: {str(e)}")

    def _send_order_notification_mail(self, mail_template):
        for order in self:
            if order.is_combined_payment_order:
                _logger.info("Skipping confirmation mail for Master Aggregator Order: %s", order.name)
                continue

            if order.website_id:
                _logger.info("Skipping standard Odoo template for Website Order: %s", order.name)
                continue

            super(SaleOrder, order)._send_order_notification_mail(mail_template)

    def _send_order_confirmation_mail(self):
        for order in self:
            if order.is_combined_payment_order:
                _logger.info("Skipping confirmation mail for Master Aggregator Order: %s", order.name)
                continue

            if order.website_id:
                _logger.info("Skipping standard Odoo template for Website Order: %s", order.name)
                continue

            super(SaleOrder, order)._send_order_confirmation_mail()

    def get_event_summary(self):
        self.ensure_one()
        result = []

        for line in self.order_line:
            if not line.event_id:
                continue

            registrations = self.env['event.registration'].sudo().search([
                ('sale_order_line_id', '=', line.id)
            ])

            attendees = []
            for reg in registrations:
                answers = {}
                for ans in reg.registration_answer_ids:
                    val = (
                        (ans.value_answer_id.name if getattr(ans, 'value_answer_id', False) else False)
                        or getattr(ans, 'value_text_box', False)
                        or getattr(ans, 'value_char', False)
                        or getattr(ans, 'value_email', False)
                        or getattr(ans, 'value_phone', False)
                        or ''
                    )
                    answers[ans.question_id.title] = val

                attendees.append({
                    'name': reg.name,
                    'answers': answers,
                })

            result.append({
                'event_name': line.event_id.name,
                'date_begin': line.event_id.date_begin,
                'date_end': line.event_id.date_end,
                'location': line.event_id.address_id.contact_address if line.event_id.address_id else '',
                'attendees': attendees,
            })

        return result

    #  _update_programs_and_rewards  (per-line, tax-aware)
    def _update_programs_and_rewards(self):
        for order in self:
            if order.is_combined_payment_order:
                _logger.info(
                    "_update_programs_and_rewards: master order %s — "
                    "checking if reward lines need to be created",
                    order.name,
                )
                existing_reward_lines = order.order_line.filtered(lambda l: l.is_reward_line)
                if not existing_reward_lines and (order.applied_coupon_ids or order.code_enabled_rule_ids):
                    _logger.info(
                        "_update_programs_and_rewards: FLOW-C — creating reward lines "
                        "manually on master %s for coupons %s and rules %s",
                        order.name,
                        order.applied_coupon_ids.mapped('code'),
                        order.code_enabled_rule_ids.mapped('code'),
                    )
                    order._create_and_propagate_rewards()
                else:
                    _logger.info(
                        "_update_programs_and_rewards: master %s — "
                        "%d reward lines already exist, preserving",
                        order.name, len(existing_reward_lines),
                    )
                continue

            # Normal (non-master) order
            pre_coupon_ids = set(order.applied_coupon_ids.ids)
            pre_rule_ids = set(order.code_enabled_rule_ids.ids)

            super(SaleOrder, order)._update_programs_and_rewards()

            # Remove auto-injected coupons/rules
            auto_coupon_ids = set(order.applied_coupon_ids.ids) - pre_coupon_ids
            auto_rule_ids = set(order.code_enabled_rule_ids.ids) - pre_rule_ids
            if auto_coupon_ids:
                order.sudo().write({'applied_coupon_ids': [(3, cid) for cid in auto_coupon_ids]})
            if auto_rule_ids:
                order.sudo().write({'code_enabled_rule_ids': [(3, rid) for rid in auto_rule_ids]})

            # Remove reward lines from auto-injected programs
            allowed_program_ids = set()
            for c in order.applied_coupon_ids:
                if c.program_id:
                    allowed_program_ids.add(c.program_id.id)
            for r in order.code_enabled_rule_ids:
                if r.program_id:
                    allowed_program_ids.add(r.program_id.id)
            if allowed_program_ids:
                for line in order.order_line.filtered(lambda l: l.is_reward_line and l.reward_id):
                    if line.reward_id.program_id.id not in allowed_program_ids:
                        line.sudo().unlink()

            # PER-LINE, TAX-AWARE traversal for each reward
            reward_line_snapshot = []
            for reward_line in order.order_line.filtered(lambda l: l.is_reward_line and l.reward_id):
                reward = reward_line.reward_id
                if reward.reward_type != 'discount' or not reward.discount:
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
                    # capture tax groups NOW while the line still exists
                    'tax_groups': order._group_discounts_by_tax(
                        order.order_line.filtered(lambda l: not l.is_reward_line),
                        reward, reward_line,
                    ),
                })

            # Collect IDs to unlink in one shot — avoids mid-loop recompute triggers
            lines_to_unlink = order.env['sale.order.line'].sudo().browse(
                [s['line_id'] for s in reward_line_snapshot]
            ).exists()
            if lines_to_unlink:
                lines_to_unlink.sudo().unlink()

            # Now create/update the correct tax-grouped reward lines
            for snap in reward_line_snapshot:
                tax_groups = snap['tax_groups']
                _logger.info(
                    "_update_programs_and_rewards: order=%s reward=%s tax_groups=%s",
                    order.name, snap['reward'].id,
                    {str(list(k)): v['amount'] for k, v in tax_groups.items()},
                )
                if not tax_groups:
                    _logger.info(
                        "_update_programs_and_rewards: No discount → skipping reward on %s",
                        order.name,
                    )
                    continue

                order._upsert_reward_lines(
                    order, snap['reward'], snap['reward_product'],
                    snap['reward_label'], snap['identifier_code'], tax_groups,
                )

            order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
            order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

    #  _create_and_propagate_rewards  (per-line, tax-aware)
    def _create_and_propagate_rewards(self):
        self.ensure_one()
        master_order = self
        linked_orders = master_order.linked_seller_order_ids

        if not linked_orders:
            _logger.warning(
                "_create_and_propagate: No linked seller orders on %s", master_order.name
            )
            return

        all_programs = (
            master_order.applied_coupon_ids.mapped('program_id')
            | master_order.code_enabled_rule_ids.mapped('program_id')
        )

        for program in all_programs:
            if not program:
                continue

            for reward in program.reward_ids:
                reward_label = (
                    getattr(reward, 'description', None)
                    or getattr(reward, 'reward_description', None)
                    or str(reward.id)
                )
                if reward.reward_type != 'discount' or not reward.discount:
                    _logger.info("_create_and_propagate: skipping non-discount reward %s", reward_label)
                    continue

                reward_product = reward.discount_line_product_id
                if not reward_product:
                    _logger.warning(
                        "_create_and_propagate: reward %s has no discount_line_product_id", reward_label)
                    continue

                identifier_code = str(reward.id)

                # Propagate coupons/rules to seller orders
                for so in linked_orders:
                    so.sudo().write({
                        'applied_coupon_ids': [(4, c) for c in master_order.applied_coupon_ids.ids],
                        'code_enabled_rule_ids': [(4, r) for r in master_order.code_enabled_rule_ids.ids],
                    })

                # Accumulate master-level tax groups across all seller orders
                master_tax_groups = {}
                total_master_discount = 0.0

                # Per seller order → per sale order line traversal
                for so in linked_orders:
                    so_regular = so.order_line.filtered(lambda l: not l.is_reward_line)
                    tax_groups = master_order._group_discounts_by_tax(so_regular, reward, None)

                    if not tax_groups:
                        _logger.info("_create_and_propagate: %s no discount → skip", so.name)
                        continue

                    seller_total = sum(g['amount'] for g in tax_groups.values())
                    total_master_discount += seller_total

                    _logger.info(
                        "_create_and_propagate: so=%s tax_groups=%s seller_total=%s",
                        so.name,
                        {str(list(k)): v['amount'] for k, v in tax_groups.items()},
                        seller_total,
                    )

                    # Write reward lines to the seller order (one per tax group)
                    so._upsert_reward_lines(
                        so, reward, reward_product, reward_label,
                        identifier_code, tax_groups,
                    )

                    # Accumulate into master tax groups
                    for key, group in tax_groups.items():
                        if key not in master_tax_groups:
                            master_tax_groups[key] = {'amount': 0.0, 'tax_ids': group['tax_ids']}
                        master_tax_groups[key]['amount'] += group['amount']

                    so.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
                    so.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

                # Write master reward lines (one per tax group)
                if master_tax_groups:
                    master_order._upsert_reward_lines(
                        master_order, reward, reward_product, reward_label,
                        identifier_code, master_tax_groups,
                    )
                    _logger.info(
                        "_create_and_propagate: master tax_groups=%s total=%s",
                        {str(list(k)): v['amount'] for k, v in master_tax_groups.items()},
                        total_master_discount,
                    )

                master_order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
                master_order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

    #  _propagate_discount_to_seller_orders_model  (per-line, tax-aware)
    def _propagate_discount_to_seller_orders_model(self):
        self.ensure_one()
        master_order = self
        linked_orders = master_order.linked_seller_order_ids
        if not linked_orders:
            _logger.warning("_propagate_model: No linked seller orders on %s", master_order.name)
            return

        master_reward_lines = master_order.order_line.filtered(
            lambda l: l.is_reward_line and l.reward_id
        )

        mrl_snapshot = []
        for master_reward_line in master_reward_lines:
            reward = master_reward_line.reward_id
            reward_label = (
                getattr(reward, 'description', None)
                or getattr(reward, 'reward_description', None)
                or str(reward.id)
            )
            if reward.reward_type != 'discount' or not reward.discount:
                _logger.info("_propagate_model: skipping non-discount reward %s", reward_label)
                continue
            reward_product = reward.discount_line_product_id
            if not reward_product:
                _logger.warning("_propagate_model: reward %s has no discount_line_product_id", reward_label)
                continue
            mrl_snapshot.append({
                'line_id': master_reward_line.id,
                'reward': reward,
                'reward_product': reward_product,
                'reward_label': reward_label,
                'rl_name': master_reward_line.name or reward_label,
                'rl_identifier': master_reward_line.reward_identifier_code or str(reward.id),
            })

        for snap in mrl_snapshot:
            reward = snap['reward']
            reward_product = snap['reward_product']
            reward_label = snap['reward_label']
            rl_name = snap['rl_name']
            rl_identifier = snap['rl_identifier']

            # Re-browse to get a live record for passing to _group_discounts_by_tax
            master_reward_line_live = master_order.env['sale.order.line'].browse(
                snap['line_id']
            ).exists()

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
                tax_groups = master_order._group_discounts_by_tax(
                    so_regular, reward, master_reward_line_live or None
                )

                if not tax_groups:
                    _logger.info("_propagate_model: %s has no discount → skip", so.name)
                    continue

                seller_total = sum(g['amount'] for g in tax_groups.values())
                total_master_discount += seller_total

                _logger.info(
                    "_propagate_model: so=%s tax_groups=%s seller_total=%s",
                    so.name,
                    {str(list(k)): v['amount'] for k, v in tax_groups.items()},
                    seller_total,
                )

                so._upsert_reward_lines(
                    so, reward, reward_product,
                    rl_name, rl_identifier,
                    tax_groups, master_reward_line_live or None,
                )

                for key, group in tax_groups.items():
                    if key not in master_tax_groups:
                        master_tax_groups[key] = {'amount': 0.0, 'tax_ids': group['tax_ids']}
                    master_tax_groups[key]['amount'] += group['amount']

                so.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
                so.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

            if master_tax_groups:
                # Unlink the original single master reward line THEN recreate tax-grouped.
                # Values already captured above — safe to unlink now.
                if master_reward_line_live:
                    master_reward_line_live.sudo().unlink()
                master_order._upsert_reward_lines(
                    master_order, reward, reward_product,
                    rl_name, rl_identifier,
                    master_tax_groups,
                )
                _logger.info(
                    "_propagate_model: master tax_groups=%s total=%s",
                    {str(list(k)): v['amount'] for k, v in master_tax_groups.items()},
                    total_master_discount,
                )

            master_order.sudo().flush_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])
            master_order.sudo().invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax', 'order_line'])

    @api.model
    def _scheduled_send_unpaid_order_reminder(self):
        """
        Scheduled action to send reminder emails for orders that remain unpaid 14 days after creation.
        Grouping split orders to avoid duplicate emails.
        """
        date_14_days_ago = fields.Date.subtract(fields.Date.today(), days=14)

        # Define the datetime range for orders created exactly 14 days ago
        start_dt = fields.Datetime.to_string(datetime.combine(date_14_days_ago, time.min))
        end_dt = fields.Datetime.to_string(datetime.combine(date_14_days_ago, time.max))

        # Search for unpaid orders from 14 days ago that haven't received a reminder
        orders = self.search([
            ('create_date', '>=', start_dt),
            ('create_date', '<=', end_dt),
            # ('state', 'in', ['draft', 'sent', 'sale']),
            ('state', '=', 'sale'),
            ('amount_total', '>', 0),
            ('unpaid_reminder_sent', '=', False),
        ])

        template = self.env.ref('multi_payment_checkout.email_template_unpaid_order_reminder', raise_if_not_found=False)
        if not template:
            _logger.warning("Email template 'multi_payment_checkout.email_template_unpaid_order_reminder' not found.")
            return

        # Tracking processed purchases to avoid duplicates in the same run
        processed_orders = self.env['sale.order']

        for order in orders:
            if order in processed_orders or order.unpaid_reminder_sent:
                continue

            # Identify all related orders (Master + Linked Sellers)
            related_orders = order
            if order.is_combined_payment_order:
                related_orders |= order.linked_seller_order_ids
            else:
                # If it's a seller order, find the master
                master = self.search([('linked_seller_order_ids', 'in', order.ids)], limit=1)
                if master:
                    related_orders |= master
                    related_orders |= master.linked_seller_order_ids

            # Skip if ANY related order is paid or has a successful transaction
            is_paid = False
            for r_order in related_orders:
                if r_order.transaction_ids.filtered(lambda tx: tx.state in ['done', 'authorized']):
                    is_paid = True
                    break
                if r_order.invoice_ids and any(
                        inv.payment_state in ['paid', 'in_payment'] for inv in r_order.invoice_ids):
                    is_paid = True
                    break

            if is_paid:
                # Mark as processed so we don't check them again
                related_orders.write({'unpaid_reminder_sent': True})
                processed_orders |= related_orders
                continue

            # Decide which order to use for the email (Master preferred)
            email_order = related_orders.filtered('is_combined_payment_order')[:1] or order

            try:
                template.send_mail(email_order.id, force_send=True,
                                   email_values={'email_from': 'taborcata@taborcata.sk'})
                _logger.info("Sent unpaid order reminder for purchase starting with %s", email_order.name)

                # Mark ALL related orders as sent
                related_orders.write({'unpaid_reminder_sent': True})
                processed_orders |= related_orders
            except Exception as e:
                _logger.error("Failed to send unpaid reminder for %s: %s", email_order.name, str(e))

    def _verify_updated_quantity(self, order_line, product_id, new_qty, event_ticket_id=False, **kwargs):
        """Restrict quantity updates for event tickets according to available seats."""
        new_qty, warning = super()._verify_updated_quantity(order_line, product_id, new_qty, **kwargs)

        if not event_ticket_id:
            if not order_line.event_ticket_id or new_qty < order_line.product_uom_qty:
                return new_qty, warning
            else:
                return order_line.product_uom_qty, _("Zvýšenie počtu táborov v rámci existujúcej objednávky nie je, bohužiaľ, možné. Prosíme Vás o vytvorenie novej objednávky.")

        # Adding new ticket to the cart (might be automatically linked to an existing line)
        ticket = self.env['event.event.ticket'].browse(event_ticket_id).exists()
        if not ticket:
            raise UserError(_("The provided ticket doesn't exist"))

        # TODO TDE consider full cart qty and not only added qty
        # if event seats are not auto confirmed.
        # Since created registrations are automatically reserved
        # We should only consider new added qty and not full quantity
        # when checking for seat availability
        existing_qty = order_line.product_uom_qty if order_line else 0
        qty_added = new_qty - existing_qty
        warning = ''
        if ticket.seats_limited and ticket.seats_available <= 0:
            # Remove existing line if exists and do not add a new one
            # if no ticket is available anymore
            new_qty = existing_qty
            warning = _(
                'Sorry, The %(ticket)s tickets for the %(event)s event are sold out.',
                ticket=ticket.name,
                event=ticket.event_id.name,
            )
        elif ticket.seats_limited and qty_added > ticket.seats_available:
            new_qty = existing_qty + ticket.seats_available
            warning = _(
                'Sorry, only %(remaining_seats)d seats are still available for the %(ticket)s ticket for the %(event)s event.',
                remaining_seats=ticket.seats_available,
                ticket=ticket.name,
                event=ticket.event_id.name,
            )

        return new_qty, warning
