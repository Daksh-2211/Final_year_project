from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_subtotal_vat = fields.Monetary(
        string='Subtotal (VAT Incl.)',
        compute='_compute_price_subtotal_vat',
        currency_field='currency_id',
        store=True
    )

    @api.depends('price_total')
    def _compute_price_subtotal_vat(self):
        for line in self:
            line.price_subtotal_vat = line.price_total