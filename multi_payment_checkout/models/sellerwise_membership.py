from odoo import models, fields, api

class SellerMembershipConfig(models.Model):
    _name = 'seller.membership.config'
    _description = 'Seller-Wise Membership Configuration'
    _rec_name = 'seller_id'

    seller_id = fields.Many2one('res.partner', string="Seller", required=True,domain=[('seller', '=', True)])
    product_id = fields.Many2one('product.product', string="Membership Product", required=True)