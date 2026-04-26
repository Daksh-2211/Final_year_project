from odoo import models, fields
from lxml import etree
import time
from odoo.tools import html2plaintext
import base64
from datetime import timedelta
import re


class AccountMove(models.Model):
    _inherit = "account.move"

    def _sanitize_pohoda_text(self, text):
        """
        અદ્રશ્ય કેરેક્ટર્સ (Zero-width space) અને અયોગ્ય સ્પેસ દૂર કરવા માટે.
        """
        if not text:
            return ""
        # U+200B (Zero Width Space) અને અન્ય અદ્રશ્ય કેરેક્ટર્સને રીમુવ કરશે
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', str(text))
        return text.strip()

    def cron_generate_pohoda_xml(self):
        """
        Cron to generate Pohoda XML for previous month invoices
        grouped by seller or company partner.
        """

        today = fields.Date.today()

        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        invoices = self.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", first_day_prev_month),
            ("invoice_date", "<=", last_day_prev_month),
        ])

        if not invoices:
            return

        seller_map = {}

        for inv in invoices:

            seller = inv.marketplace_seller_id or inv.company_id.partner_id

            if seller not in seller_map:
                seller_map[seller] = self.env["account.move"]

            seller_map[seller] |= inv

        for seller, invs in seller_map.items():
            xml = invs.generate_pohoda_xml(seller)

            file_name = f"pohoda_export_{seller.name}_{first_day_prev_month}_{last_day_prev_month}.xml"

            self.env["ir.attachment"].create({
                "name": file_name,
                "type": "binary",
                "datas": base64.b64encode(xml),
                "mimetype": "application/xml",
            })

    def to_pohoda_vs(self, invoice_number):
        numeric_only = re.sub(r'\D', '', invoice_number or "")
        return numeric_only[-10:]

    def generate_pohoda_xml(self, seller):
        NS_DATA = "http://www.stormware.cz/schema/version_2/data.xsd"
        NS_INVOICE = "http://www.stormware.cz/schema/version_2/invoice.xsd"
        NS_TYPE = "http://www.stormware.cz/schema/version_2/type.xsd"

        NSMAP = {
            None: NS_DATA,
            "ns1": NS_INVOICE,
            "ns2": NS_TYPE,
        }

        export_id = str(int(time.time()))
        root = etree.Element(
            "{%s}dataPack" % NS_DATA,
            nsmap=NSMAP,
            version="2.0",
            id=export_id,
            ico=seller.company_registry or seller.vat or "",
            application="Odoo",
            note="Zoznam dokladov",
        )

        for invoice in self:
            pack = etree.SubElement(root, "{%s}dataPackItem" % NS_DATA, version="2.0", id=str(invoice.id))
            inv = etree.SubElement(pack, "{%s}invoice" % NS_INVOICE, version="2.0")

            # --- HEADER ---
            header = etree.SubElement(inv, "{%s}invoiceHeader" % NS_INVOICE)
            etree.SubElement(header, "{%s}id" % NS_INVOICE).text = str(invoice.id)
            etree.SubElement(header, "{%s}invoiceType" % NS_INVOICE).text = "issuedInvoice"

            number = etree.SubElement(header, "{%s}number" % NS_INVOICE)
            etree.SubElement(number, "{%s}numberRequested" % NS_TYPE).text = invoice.name or ""

            symvar = self.to_pohoda_vs(invoice.name)
            etree.SubElement(header, "{%s}symVar" % NS_INVOICE).text = symvar
            etree.SubElement(header, "{%s}originalDocument" % NS_INVOICE).text = invoice.name or ""

            inv_date = str(invoice.invoice_date or "")
            etree.SubElement(header, "{%s}date" % NS_INVOICE).text = inv_date
            etree.SubElement(header, "{%s}dateTax" % NS_INVOICE).text = inv_date
            etree.SubElement(header, "{%s}dateAccounting" % NS_INVOICE).text = inv_date
            etree.SubElement(header, "{%s}dateDue" % NS_INVOICE).text = str(invoice.invoice_date_due or inv_date)
            etree.SubElement(header, "{%s}dateDelivery" % NS_INVOICE).text = inv_date

            class_kv = etree.SubElement(header, "{%s}classificationKVDPH" % NS_INVOICE)
            etree.SubElement(class_kv, "{%s}ids" % NS_TYPE).text = "D2"

            clean_seller_name = self._sanitize_pohoda_text(seller.name or "Faktúra")
            etree.SubElement(header, "{%s}text" % NS_INVOICE).text = clean_seller_name

            # etree.SubElement(header, "{%s}text" % NS_INVOICE).text = seller.name or "Faktúra"

            # --- PARTNER IDENTITY ---
            partner = etree.SubElement(header, "{%s}partnerIdentity" % NS_INVOICE)
            addr = etree.SubElement(partner, "{%s}address" % NS_TYPE)

            etree.SubElement(addr, "{%s}name" % NS_TYPE).text = self._sanitize_pohoda_text(invoice.partner_id.name)
            # etree.SubElement(addr, "{%s}name" % NS_TYPE).text = invoice.partner_id.name or ""
            etree.SubElement(addr, "{%s}city" % NS_TYPE).text = invoice.partner_id.city or ""
            etree.SubElement(addr, "{%s}street" % NS_TYPE).text = invoice.partner_id.street or ""
            etree.SubElement(addr, "{%s}zip" % NS_TYPE).text = (invoice.partner_id.zip or "").replace(" ", "")
            if invoice.partner_id.country_id:
                country = etree.SubElement(addr, "{%s}country" % NS_TYPE)
                etree.SubElement(country, "{%s}ids" % NS_TYPE).text = invoice.partner_id.country_id.code or ""

            # --- MY IDENTITY ---
            my_id = etree.SubElement(header, "{%s}myIdentity" % NS_INVOICE)
            m_addr = etree.SubElement(my_id, "{%s}address" % NS_TYPE)
            # etree.SubElement(m_addr, "{%s}company" % NS_TYPE).text = seller.name or ""

            etree.SubElement(m_addr, "{%s}company" % NS_TYPE).text = self._sanitize_pohoda_text(seller.name)

            etree.SubElement(m_addr, "{%s}city" % NS_TYPE).text = seller.city or ""
            etree.SubElement(m_addr, "{%s}street" % NS_TYPE).text = seller.street or ""
            etree.SubElement(m_addr, "{%s}zip" % NS_TYPE).text = (seller.zip or "").replace(" ", "")
            etree.SubElement(m_addr, "{%s}ico" % NS_TYPE).text = seller.company_registry or ""

            dic_val = (seller.vat or "").replace("SK", "")
            etree.SubElement(m_addr, "{%s}dic" % NS_TYPE).text = dic_val
            if seller.vat:
                etree.SubElement(m_addr, "{%s}icDph" % NS_TYPE).text = seller.vat

            pay_type = etree.SubElement(header, "{%s}paymentType" % NS_INVOICE)
            etree.SubElement(pay_type, "{%s}paymentType" % NS_TYPE).text = "draft"

            # --- SUMMARY TRACKING ---
            total_untaxed_high = 0.0
            total_tax_high = 0.0
            total_untaxed_low = 0.0
            total_tax_low = 0.0

            # --- DETAIL (Items) ---
            detail = etree.SubElement(inv, "{%s}invoiceDetail" % NS_INVOICE)

            for line in invoice.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue

                item = etree.SubElement(detail, "{%s}invoiceItem" % NS_INVOICE)
                line_text = self._sanitize_pohoda_text(line.name or line.product_id.name)
                etree.SubElement(item, "{%s}text" % NS_INVOICE).text = line_text

                # etree.SubElement(item, "{%s}text" % NS_INVOICE).text = line.name or line.product_id.name or ""
                etree.SubElement(item, "{%s}quantity" % NS_INVOICE).text = str(line.quantity)

                # VAT Calculation logic
                tax_amount = line.price_total - line.price_subtotal
                tax_rate_percent = 0
                if line.price_subtotal:
                    tax_rate_percent = round((tax_amount / line.price_subtotal) * 100)

                if tax_rate_percent == 23:
                    rate_str, percent_str = "high", "23"
                    total_untaxed_high += line.price_subtotal
                    total_tax_high += tax_amount
                elif tax_rate_percent in [19, 5]:
                    rate_str, percent_str = "low", str(int(tax_rate_percent))
                    total_untaxed_low += line.price_subtotal
                    total_tax_low += tax_amount
                else:
                    rate_str, percent_str = "none", "0"

                etree.SubElement(item, "{%s}rateVAT" % NS_INVOICE).text = rate_str
                etree.SubElement(item, "{%s}percentVAT" % NS_INVOICE).text = percent_str

                # Discount Logic: Explicitly tell Pohoda about the discount percentage
                if line.discount:
                    etree.SubElement(item, "{%s}discountPercentage" % NS_INVOICE).text = "{:.2f}".format(line.discount)

                hc = etree.SubElement(item, "{%s}homeCurrency" % NS_INVOICE)
                # unitPrice is the original price before discount
                etree.SubElement(hc, "{%s}unitPrice" % NS_TYPE).text = "{:.2f}".format(line.price_unit)
                # price is the subtotal (quantity * unitPrice - discount)
                etree.SubElement(hc, "{%s}price" % NS_TYPE).text = "{:.2f}".format(line.price_subtotal)
                etree.SubElement(hc, "{%s}priceVAT" % NS_TYPE).text = "{:.2f}".format(tax_amount)
                etree.SubElement(hc, "{%s}priceSum" % NS_TYPE).text = "{:.2f}".format(line.price_total)

            # --- DYNAMIC SUMMARY ---
            summary = etree.SubElement(inv, "{%s}invoiceSummary" % NS_INVOICE)
            h_curr_sum = etree.SubElement(summary,
                                          "{%s}homeCurrency" % NS_TYPE)  # Note: ns2/type namespace is safer here

            etree.SubElement(h_curr_sum, "{%s}priceSum" % NS_TYPE).text = "{:.2f}".format(invoice.amount_total)
            etree.SubElement(h_curr_sum, "{%s}priceHigh" % NS_TYPE).text = "{:.2f}".format(total_untaxed_high)
            etree.SubElement(h_curr_sum, "{%s}priceHighVAT" % NS_TYPE).text = "{:.2f}".format(total_tax_high)
            etree.SubElement(h_curr_sum, "{%s}priceLow" % NS_TYPE).text = "{:.2f}".format(total_untaxed_low)
            etree.SubElement(h_curr_sum, "{%s}priceLowVAT" % NS_TYPE).text = "{:.2f}".format(total_tax_low)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
