###################################################################################
#
#    Copyright (c) 2022 Data Dance s.r.o.
#
#    Data Dance Proprietary License v1.0
#
#    This software and associated files (the "Software") may only be used
#    (executed, modified, executed after modifications) if you have
#    purchased a valid license from Data Dance s.r.o.
#
#    The above permissions are granted for a single database per purchased
#    license. Furthermore, with a valid license it is permitted to use the
#    software on other databases as long as the usage is limited to a testing
#    or development environment.
#
#    You may develop modules based on the Software or that use the Software
#    as a library (typically by depending on it, importing it and using its
#    resources), but without copying any source code or material from the
#    Software. You may distribute those modules under the license of your
#    choice, provided that this license is compatible with the terms of the
#    Data Dance Proprietary License (For example: LGPL, MIT, or proprietary
#    licenses similar to this one).
#
#    It is forbidden to publish, distribute, sublicense, or sell copies of
#    the Software or modified copies of the Software.
#
#    The above copyright notice and this permission notice must be included
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
###################################################################################

import base64
import logging
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import requests
from odoo import _, api, fields, models
from odoo.addons.payment_comgate.const import (
    MINIMAL_AMOUNT,
    REFUND_ERRORS,
    SUPPORTED_CURRENCIES,
)
from odoo.exceptions import ValidationError
from odoo.fields import Command
from PIL import Image
from werkzeug.urls import url_join

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("comgate", "Comgate")],
        ondelete={"comgate": "set default"},
    )
    comgate_key_id = fields.Char(
        string="Comgate Key Id",
        help="The key solely used to identify the account with Comgate.",
        required_if_provider="comgate",
    )
    comgate_key_secret = fields.Char(
        string="Comgate Key Secret",
        required_if_provider="comgate",
        groups="base.group_system",
    )
    ip_control = fields.Selection(
        selection=[
            ("without", "Without control (not recommended)"),
            ("http_headers", "HTTP headers"),
            ("source_ip", "Source IP"),
        ],
        string="IP Control",
        required_if_provider="comgate",
        groups="base.group_system",
        default="without",
    )
    http_header = fields.Char(
        string="HTTP Header",
        default="X-Forwarded-For",
        help="HTTP header used for IP control.",
        groups="base.group_system",
    )

    # === COMPUTE METHODS ===#

    def _compute_feature_support_fields(self):
        """Override of `payment` to enable additional features."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == "comgate").update(
            {
                "support_manual_capture": "partial",
                "support_refund": "partial",
            }
        )

    # === ACTIONS ===#
    def action_update_comgate_methods(self):
        try:
            url = "https://payments.comgate.cz/v1.0/methods"
            params = {
                "merchant": self.comgate_key_id,
                "secret": self.comgate_key_secret,
                "type": "json",
                "lang": "en",
            }
            response = requests.post(url, params=params)
            response.raise_for_status()
            response = response.json()

            if "methods" in response:
                methods = response["methods"]

                # get all ids from the response
                ids = [method["id"] for method in methods]

                # get all existing methods where provider is comgate
                existing_ids = self.env["payment.method"].search([])
                existing_ids = existing_ids.filtered(
                    lambda x: self.id in x.provider_ids.ids
                ).mapped("code")
                ids_to_delete = list(set(existing_ids) - set(ids))

                # delete methods that are not in the response
                self.env["payment.method"].search(
                    [("code", "in", ids_to_delete)]
                ).unlink()

                # create or update methods
                for method in methods:
                    # check if method exists
                    existing_method = self.env["payment.method"].search(
                        [("code", "=", method["id"])]
                    )
                    if "logo" in method:
                        logo = self.get_image_from_url(method["logo"])
                        image_bytes = base64.b64decode(logo)
                        image_buffer = BytesIO(image_bytes)
                        image = Image.open(image_buffer)
                        resized_image = image.resize((300, 120))
                        resized_image_buffer = BytesIO()
                        resized_image.save(resized_image_buffer, format="PNG")

                        resized_base64_image = base64.b64encode(
                            resized_image_buffer.getvalue()
                        ).decode("utf-8")
                        logo = resized_base64_image
                    if existing_method:
                        # update method
                        existing_method.write(
                            {
                                "name": method["name"],
                                "image": logo if logo else False,
                            }
                        )
                    else:
                        # create method
                        self.env["payment.method"].create(
                            {
                                "code": method["id"],
                                "name": method["name"],
                                "provider_ids": [Command.link(self.id)],
                                "image": logo if logo else False,
                                "support_refund": "partial",
                            }
                        )
        except Exception as e:
            _logger.warning(f"Error occurred while updating Comgate methods: {e}")

    # === BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """Override of `payment` to filter out Comgate providers for unsupported currencies."""
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, **kwargs
        )

        currency = self.env["res.currency"].browse(currency_id).exists()
        if currency and currency.name not in SUPPORTED_CURRENCIES:
            providers = providers.filtered(lambda p: p.code != "comgate")

        if currency and currency.name in MINIMAL_AMOUNT:
            if args[2] < MINIMAL_AMOUNT[currency.name]:
                providers = providers.filtered(lambda p: p.code != "comgate")

        return providers

    def _comgate_make_request(self, endpoint, payload=None):
        self.ensure_one()
        url = url_join("https://payments.comgate.cz/v1.0/", endpoint)
        auth = {
            "merchant": self.comgate_key_id,
            "secret": self.comgate_key_secret,
        }
        if payload:
            payload.update(auth)
            response = requests.post(url, params=payload, timeout=25)
            response.raise_for_status()
            if endpoint == "refund":
                code = re.search(r"code=(\w+)", response.text).group(1)
                if code != "0":
                    raise ValidationError(
                        "Comgate: " + _(REFUND_ERRORS.get(code, "Unknown error"))
                    )
            elif endpoint == "create":
                response_data = parse_qs(response.text)
                redirect_url = response_data.get("redirect", [""])[0]
                if redirect_url:
                    redirect_url = urlparse(redirect_url)
                    redirect_url = redirect_url.geturl()
                    return redirect_url
                else:
                    message = response_data.get("message", [""])[0]
                    if message:
                        raise ValidationError("Comgate: " + _(message))
                    raise ValidationError(
                        "Comgate: " + _("Received incomplete transaction data.")
                    )
            return True
        return False

    # === HELPER METHODS ===#
    def get_image_from_url(self, url):
        try:
            data = base64.b64encode(requests.get(url.strip()).content).replace(
                b"\n", b""
            )
            return data
        except Exception as e:
            _logger.warning("Can’t load the image from URL %s" % url)
            logging.exception(e)
        return None
