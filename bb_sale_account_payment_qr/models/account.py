import base64
import logging

import werkzeug.exceptions
import werkzeug.urls

from odoo import api, fields, models
from odoo.tools.image import image_data_uri

_logger = logging.getLogger(__name__)

class account_move(models.Model):
    _inherit = 'account.move'

    payment_link_url = fields.Char("Payment Link URL", compute="_compute_payment_link_url")

    def get_payment_link_url_ok(self):
        return self.amount_residual > 0 and self.move_type == "out_invoice"

    def get_payment_link_url_button(self):
        config = self.env["ir.config_parameter"].sudo()
        return (
            config.get_param("bb_link_on_invoice_button") == "True"
            and self.get_payment_link_url_ok()
        )

    def get_payment_link_url_qrcode(self):
        config = self.env["ir.config_parameter"].sudo()
        return (
            config.get_param("bb_link_on_invoice_qr_code") == "True"
            and self.get_payment_link_url_ok()
        )

    def _compute_payment_link_url(self):
        for item in self:
            if self.get_payment_link_url_ok():
                try:
                    share_link = item.get_base_url() + item.get_portal_url()
                    item.payment_link_url = share_link
                except Exception as e:
                    _logger.error("Error computing payment link URL for invoice %s: %s", item.id, e)
                    item.payment_link_url = False
            else:
                item.payment_link_url = False

    @api.model
    def build_qr_code_base64(self):
        try:
            link_url = self.payment_link_url or ""
            barcode = self.env["ir.actions.report"].barcode(
                "QR", link_url, width=128, height=128, humanreadable=1
            )
        except (ValueError, AttributeError):
            raise werkzeug.exceptions.HTTPException(description="Cannot convert into barcode.")
        return image_data_uri(base64.b64encode(barcode))