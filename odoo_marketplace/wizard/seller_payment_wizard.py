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
import datetime
import logging
_logger = logging.getLogger(__name__)


class SellerPaymentWizard(models.TransientModel):
    _name = 'seller.payment.wizard'
    _description = "Seller Payment Wizard"

    @api.model
    def _get_seller(self):
        """ Get active seller id"""
        if self._context.get('active_model',False) and self._context.get('active_model') == 'res.partner':
            result = self.env['res.partner'].browse(
                self._context.get('active_id', False)).id
        else:
            partner_id = self.env.user.partner_id
            result = partner_id.id if partner_id.seller and partner_id.state == 'approved' else False
        return result

    @api.model
    def _get_payment_method(self):
        seller_id = self.env['res.partner'].browse(self._context.get('active_id', False))
        if seller_id and seller_id.payment_method:
            payment_method = seller_id.payment_method.ids[0]
        else:
            try:
                payment_method_cheque_id = self.env['ir.model.data'].check_object_reference(
                    'odoo_marketplace', 'marketplace_seller_payment_method_data1')
                if payment_method_cheque_id:
                    payment_method = payment_method_cheque_id[1]
            except Exception as e:
                _logger.warning("Warning! Cash seller payment method not found (%r)",e)
                pass
        return payment_method if payment_method else False

    @api.depends('seller_id')
    def get_cashable_amount(self):
        """ Get cashable amount on the basis of seller"""
        if self._context.get('active_id', False):
            seller_obj = self.env['res.partner'].browse(self._context.get('active_id', False))
        else:
            seller_obj = self.seller_id
        self.cashable_amount = seller_obj.cashable_amount
        self.currency_id = seller_obj.seller_currency_id

    seller_id = fields.Many2one(
        "res.partner", string="Seller", default=_get_seller, domain=[("seller", "=", True), ("state", "=", "approved")])
    amount = fields.Float(string="Payment Amount")
    cashable_amount = fields.Float(
        string="Cashable Amount", compute="get_cashable_amount")
    payment_method_id = fields.Many2one("seller.payment.method", string="Payment Method", help="Select payment method in which you have paid payment to seller.", copy=False, default=_get_payment_method)
    memo = fields.Char(string="Memo", copy=False)
    description = fields.Text(string="Payment Description",  translate=True, copy=False)
    date = fields.Date(string="Date", default=fields.Date.context_today)
    currency_id = fields.Many2one("res.currency", "Marketplace Currency", compute="get_cashable_amount")

    def validate_payment_request(self):
        """ Validate payment request on the basis of seller_payment_limit and next payment request limit"""
        if len(self) > 1:
            self.ensure_one()
        seller_payment_obj = self.env["seller.payment"].search(
            [("seller_id", "=", self.seller_id.id), ("state", "=", "posted")], limit=1)
        seller_payment_limit = self.seller_id.get_seller_global_fields('seller_payment_limit')
        if seller_payment_obj:
            last_payment_date = seller_payment_obj.date.date()
            today_date = datetime.datetime.today().date()
            days_diff = today_date - last_payment_date
            if days_diff.days >= self.seller_id.get_seller_global_fields('next_payment_request') and self.amount >= seller_payment_limit and self.amount <= self.seller_id.cashable_amount:
                return True
            else:
                return False
        else:
            if self.amount >= seller_payment_limit and self.amount <= self.seller_id.cashable_amount:
                return True
            else:
                return False

    def is_payment_request_pending(self):
        """This method checks wheather any seller payment request is pending"""
        if len(self) > 1:
            self.ensure_one()
        seller_payment_obj = self.env["seller.payment"].search([("seller_id", "=", self.seller_id.id), (
            "state", "in", ["requested", "confirm"]), ("payment_mode", "=", "seller_payment")], limit=1)
        if seller_payment_obj:
            return True
        return False

    def do_request(self):
        """ Create seller payment request"""
        msg = False
        self.ensure_one()
        if self.cashable_amount < 0:
            if self._context.get("by_seller", False):
                msg = _("You can't request for payment now, due to insufficient amount.")
            else:
                msg = _("You can't payment now to this seller, due to insufficient amount.")
        if self.amount > self.cashable_amount:
            if self._context.get("by_seller", False):
                msg = _("You can't request amount more than cashable amount.")
            else:
                msg = _("You can't pay amount more than cashable amount.")
        if round(self.amount, 2) <= 0:
            if self._context.get("by_seller", False):
                msg = _("Requested amount should be greater than 0. ")
            else:
                msg = _("Paying amount should be greater than 0. ")
        if self.is_payment_request_pending():
            if self._context.get("by_seller", False):
                msg = _("Your one request of payment is not done yet, so please wait...")
            else:
                msg = _("One request of payment is not done yet for this seller, so please wait...")
        if not msg and self.validate_payment_request():
            vals = {
                "date" : self.date,
                "seller_id": self.seller_id.id,
                "payment_method": self.payment_method_id.id or self.seller_id.payment_method.ids[0] if self.seller_id.payment_method else False,
                "payment_mode": "seller_payment",
                "description": self.description or  _("Seller requested for payment..."),
                "payment_type": "dr",
                "state": "draft",
                "memo" : self.memo,
                "payable_amount": self.amount,
            }
            payment_id = self.env["seller.payment"].sudo().create(vals)
            return {
                'name': _('Sellers Payment'),
                'view_mode': 'list',
                'res_model': 'seller.payment',
                'type': 'ir.actions.act_window',
                'views': [(False, 'list'), (False, 'form')],
                'context': "{'search_default_on_going_payments_filter': 1, 'search_default_seller_filter': 1}",
            }
        elif not msg:
            if self._context.get("by_seller", False):
                msg = _("You can't request now due to one of following reason,\n 1. Amount is less than the amount limit.  OR\n 2. Minimum gap for next payment is not followed.")
            else:
                msg = _("You can't pay to this seller now due to one of following reason,\n 1. Amount is less than the amount limit.  OR\n 2. Minimum gap for next payment is not followed.")
        msg = "<p style='font-size: 15px'>" + msg + "</p>"
        return self.env["mp.wizard.message"].generated_message(msg, "Warning")

    @api.onchange('seller_id')
    def set_domain_payment_method(self):
        """ Set payment method on changing seller"""
        if self.seller_id:
            payment_methods = self.seller_id.payment_method
            self.payment_method_id = payment_methods and payment_methods[0].id
            return {'domain':{'payment_method_id':[('id','in',payment_methods.ids)]}}
