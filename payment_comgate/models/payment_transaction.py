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


from odoo import _, models
from odoo.exceptions import ValidationError


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to return comgate-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the
                                       transaction.
        :return: The dict of provider-specific rendering values.
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != "comgate" or self.operation in (
            "online_token",
            "offline",
        ):
            return res

        if self.amount < 0.1:
            raise ValidationError("Comgate: " + _("The amount is too low."))
        payload = {
            "merchant": self.provider_id.comgate_key_id,
            "test": "true" if self.provider_id.state == "test" else "false",
            "method": self.payment_method_id.code if self.payment_method_id else "ALL",
            "preauth": "true" if self.provider_id.capture_manually else "false",
            "price": int(self.amount * 100),
            "curr": self.currency_id.name,
            "label": self.reference,
            "refId": self.reference,
            "email": self.partner_email,
            "prepareOnly": "true",
            "secret": self.provider_id.comgate_key_secret,
        }
        redirect_url = self.provider_id._comgate_make_request(
            "create",
            payload,
        )
        return {"redirect_url": redirect_url}

    def _send_void_request(self, amount_to_void=None):
        """Override of `payment` to send a void request to Comgate.

        Note: self.ensure_one()

        :return: None
        """
        super()._send_void_request(amount_to_void=amount_to_void)
        if self.provider_code != "comgate":
            return

        if self.provider_reference:
            request = self.provider_id._comgate_make_request(
                "cancelPreauth",
                {
                    "transId": self.provider_reference,
                },
            )
            if request is True:
                if amount_to_void == self.amount:
                    self._set_canceled()
        else:
            raise ValidationError(
                "Comgate: " + _("Received incomplete void transaction data.")
            )

    def _send_capture_request(self, amount_to_capture=None):
        """Override of `payment` to send a capture request to Comgate.

        Note: self.ensure_one()

        :return: None
        """
        super()._send_capture_request(amount_to_capture=amount_to_capture)
        if self.provider_code != "comgate":
            return
        if self.state == "authorized":
            if self.provider_reference:
                request = self.provider_id._comgate_make_request(
                    "capturePreauth",
                    {
                        "amount": (
                            int(amount_to_capture * 100)
                            if amount_to_capture
                            else int(self.amount * 100)
                        ),
                        "transId": self.provider_reference,
                    },
                )
                if request is True:
                    self._set_done()
            else:
                raise ValidationError(
                    "Comgate: " + _("Received incomplete capture transaction data.")
                )
        else:
            raise ValidationError("Comgate: " + _("Payment status must be authorized."))

    def _send_refund_request(self, amount_to_refund=None):
        """Override of `payment` to send a refund request to Comgate.

        Note: self.ensure_one()

        :param float amount_to_refund: The amount to refund.
        :return: The refund transaction created to process the refund request.
        :rtype: recordset of `payment.transaction`
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != "comgate":
            return refund_tx

        if self.state != "done":
            raise ValidationError("Comgate: " + _("Payment status must be done."))

        if self.provider_reference:
            try:
                request = self.provider_id._comgate_make_request(
                    "refund",
                    {
                        "amount": int(amount_to_refund * 100),
                        "transId": self.provider_reference,
                        "curr": self.currency_id.name,
                        "test": "true" if self.provider_id.state == "test" else "false",
                        "refId": self.reference,
                    },
                )
                refund_tx._set_done()
            except ValidationError as e:
                raise e
            except Exception as e:
                print(e)
                raise ValidationError("Comgate: " + _("Other error occured"))

        else:
            raise ValidationError(
                "Comgate: " + _("Received incomplete refund transaction data.")
            )
        return refund_tx
