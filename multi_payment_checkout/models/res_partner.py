from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    seller_tax_id = fields.Char(string="Tax ID")