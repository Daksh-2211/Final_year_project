from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_subtotal_vat = fields.Monetary(
        string='Subtotal (VAT Incl.)',
        compute='_compute_price_subtotal_vat',
        currency_field='currency_id',
        store=True
    )

    @api.depends('price_total')
    def _compute_price_subtotal_vat(self):
        for line in self:
            # price_total in Odoo is the amount including taxes
            line.price_subtotal_vat = line.price_total