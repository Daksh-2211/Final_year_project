from odoo import models, fields, api, _

class SellerInvoiceSequence(models.Model):
    _name = 'seller.invoice.sequence'
    _description = 'Seller Invoice Sequence Numbering'
    _rec_name = 'seller_id'

    seller_id = fields.Many2one(
        'res.partner',
        string="Seller",
        domain=[('seller', '=', True)],
        required=True
    )
    seller_count = fields.Integer(string="Seller Count", readonly=True, copy=False)

    _sql_constraints = [
        ('seller_uniq', 'unique (seller_id)', 'Numbering for this seller already exists!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('seller_count'):
                # Requirements: 1 is reserved for default/no seller, so start from 2
                max_count = self.search([], order='seller_count desc', limit=1).seller_count or 1
                vals['seller_count'] = max_count + 1
        return super().create(vals_list)

    def unlink(self):
        res = super(SellerInvoiceSequence, self).unlink()
        self._resequence_seller_counts()
        return res

    def _resequence_seller_counts(self):
        all_records = self.search([], order='id asc')
        current_count = 2
        for record in all_records:
            if record.seller_count != current_count:
                record.write({'seller_count': current_count})
            current_count += 1

    def name_get(self):
        return [(rec.id, f"{rec.seller_id.name} ({rec.seller_count})") for rec in self]