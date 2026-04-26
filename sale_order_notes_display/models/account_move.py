from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    sale_order_note = fields.Html(
        string='Customer Order Note',
        compute='_compute_sale_order_note',
        store=False,
    )

    @api.depends('invoice_line_ids')
    def _compute_sale_order_note(self):
        for move in self:
            note = False
            # Find linked sale orders via invoice lines
            sale_orders = move.invoice_line_ids.sale_line_ids.order_id
            if not sale_orders:
                # Try alternate path for Odoo 18
                sale_orders = self.env['sale.order'].search([
                    ('invoice_ids', 'in', move.ids)
                ], limit=1)
            if sale_orders:
                first_order = sale_orders[0]
                note = first_order.note
            move.sale_order_note = note
