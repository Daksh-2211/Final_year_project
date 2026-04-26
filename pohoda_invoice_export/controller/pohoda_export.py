from odoo import http
from odoo.http import request
import base64
import unicodedata


class PohodaExportController(http.Controller):

    @http.route('/pohoda/export/<int:attachment_id>', type='http', auth='user')
    def download_pohoda(self, attachment_id=None, **kw):
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)

        filecontent = base64.b64decode(attachment.datas)

        filename = attachment.name
        filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()

        headers = [
            ('Content-Type', 'application/xml'),
            ('Content-Disposition', f'attachment; filename="{filename}"')
        ]

        return request.make_response(filecontent, headers)
