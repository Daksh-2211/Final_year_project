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

import logging

from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden

_logger = logging.getLogger(__name__)


class ComgateController(http.Controller):
    _return_url = "/payment/comgate/return"

    @http.route(
        _return_url,
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        save_session=False,
    )
    def comgate_callback(self, **data):
        _logger.info("Comgate Headers: %s", request.httprequest.headers)
        provider = (
            request.env["payment.provider"]
            .sudo()
            .search([("code", "=", "comgate")], limit=1)
        )
        if not provider:
            _logger.warning("Comgate: Provider does not exist")
            raise Forbidden()
        if provider.ip_control == "source_ip":
            if request.httprequest.remote_addr != "89.185.236.55":
                _logger.warning(
                    "Comgate: Source IP %s does not match the expected value 89.185.236.55",
                    request.httprequest.remote_addr,
                )
        elif provider.ip_control == "http_headers":
            if "89.185.236.55" not in request.httprequest.headers.get(
                provider.http_header, ""
            ):
                _logger.warning(
                    "Comgate: HTTP Header '%s' with value '%s' does not contain the expected value of '89.185.236.55'",
                    provider.http_header,
                    request.httprequest.headers.get(provider.http_header, ""),
                )
                raise Forbidden()
        if data:
            transaction = (
                request.env["payment.transaction"]
                .sudo()
                .search([("reference", "=", data.get("refId"))])
            )
            _logger.warning("DATA RECEIVED: %s", data)
            _logger.warning("FOUND TRANSACTION: %s", transaction)
            if transaction and "status" in data:
                if data["status"] == "PAID":
                    transaction._set_done()
                elif data["status"] == "PENDING":
                    transaction._set_pending()
                elif data["status"] == "CANCELLED":
                    transaction._set_canceled()
                elif data["status"] == "AUTHORIZED":
                    transaction._set_authorized()
                else:
                    transaction._set_error(
                        "Comgate: Received data with invalid status",
                    )
            if "transId" in data:
                transaction.provider_reference = data["transId"]

        return "code=0&message=OK"