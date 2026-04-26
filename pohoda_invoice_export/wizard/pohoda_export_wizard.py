from odoo import models, fields, api
import base64
import zipfile
from io import BytesIO
from odoo.exceptions import UserError


class PohodaExportWizard(models.TransientModel):
    _name = "pohoda.export.wizard"
    _description = "Export Invoices to Pohoda XML"

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    seller_id = fields.Many2one(
        'res.partner',
        string="Seller",
        domain=lambda self: [
            "|",
            ("seller", "=", True),
            ("id", "=", self.env.company.partner_id.id)
        ])

    def export_xml(self):

        base_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]

        buffer = BytesIO()
        zip_file = zipfile.ZipFile(buffer, "w")

        invoices_found = False

        # -------------------
        # CASE 1: Seller selected
        # -------------------
        if self.seller_id:

            invoices = self.env["account.move"].search(base_domain + [
                "|",
                ("marketplace_seller_id", "=", self.seller_id.id),
                "&",
                ("marketplace_seller_id", "=", False),
                ("company_id.partner_id", "=", self.seller_id.id),
            ])

            if invoices:
                invoices_found = True

                xml = invoices.generate_pohoda_xml(self.seller_id)

                file_name = f"pohoda_export_{self.seller_id.name.replace(' ', '_')}.xml"

                zip_file.writestr(file_name, xml)

        # -------------------
        # CASE 2: Seller not selected
        # -------------------
        else:

            invoices = self.env["account.move"].search(base_domain)

            if not invoices:
                raise UserError("No invoices found for the selected date range.")

            seller_map = {}

            for inv in invoices:

                seller = inv.marketplace_seller_id or inv.company_id.partner_id

                if seller not in seller_map:
                    seller_map[seller] = self.env["account.move"]

                seller_map[seller] |= inv

            for seller, invs in seller_map.items():
                invoices_found = True

                xml = invs.generate_pohoda_xml(seller)

                file_name = f"pohoda_export_{seller.name.replace(' ', '_')}.xml"

                zip_file.writestr(file_name, xml)

        if not invoices_found:
            raise UserError("No invoices found for the selected criteria.")

        zip_file.close()

        attachment = self.env["ir.attachment"].create({
            "name": "pohoda_export.zip",
            "type": "binary",
            "datas": base64.b64encode(buffer.getvalue()),
            "mimetype": "application/zip",
        })

        return {
            "type": "ir.actions.client",
            "tag": "pohoda_download",
            "params": {
                "url": "/pohoda/export/%s" % attachment.id
            }
        }
