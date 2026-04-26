from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Ensure Invoice knows who the Seller is (to print their IČO)
    marketplace_seller_id = fields.Many2one('res.partner', string="Seller")
    duplicate_name_warning = fields.Boolean(compute="_compute_duplicate_name_warning")

    def _get_last_sequence_domain(self, relaxed=False):
        where_string, param = super(AccountMove, self)._get_last_sequence_domain(relaxed)

        if self.move_type not in ('out_invoice', 'out_refund'):
            return where_string, param

        # 1. Determine the expected prefix for this specific move
        count = 1
        if self.marketplace_seller_id:
            seller_config = self.env['seller.invoice.sequence'].search(
                [('seller_id', '=', self.marketplace_seller_id.id)], limit=1)
            count = seller_config.seller_count if seller_config else 1

        prefix_str = 'RINV' if self.move_type == 'out_refund' else 'INV'

        # Include year/month so the domain matches only the current period,
        move_date = self.invoice_date or self.date or fields.Date.context_today(self)
        year_month = move_date.strftime('%Y/%m')
        prefix_pattern = f"{prefix_str}/{count}/{year_month}/%%"

        # 2. Update the SQL domain
        if self.marketplace_seller_id:
            where_string += """ 
                AND marketplace_seller_id = %(marketplace_seller_id)s 
                AND name LIKE %(prefix_pattern)s 
            """
            param['marketplace_seller_id'] = self.marketplace_seller_id.id
            param['prefix_pattern'] = prefix_pattern
        else:
            where_string += f""" 
                AND marketplace_seller_id IS NULL 
                AND name LIKE '{prefix_str}/1/%%' 
            """

        return where_string, param

    def _get_starting_sequence(self):
        if self.move_type in ('out_invoice', 'out_refund'):
            count = 1
            if self.marketplace_seller_id:
                seller_config = self.env['seller.invoice.sequence'].search(
                    [('seller_id', '=', self.marketplace_seller_id.id)], limit=1)
                count = seller_config.seller_count if seller_config else 1

            move_date = self.invoice_date or self.date or fields.Date.context_today(self)
            year_month = move_date.strftime('%Y/%m')

            prefix_str = 'RINV' if self.move_type == 'out_refund' else 'INV'
            return f"{prefix_str}/{count}/{year_month}/0000"

        return super(AccountMove, self)._get_starting_sequence()

    def _compute_split_sequence(self):
        super(AccountMove, self)._compute_split_sequence()
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                count = 1
                if move.marketplace_seller_id:
                    seller_config = self.env['seller.invoice.sequence'].search(
                        [('seller_id', '=', move.marketplace_seller_id.id)], limit=1)
                    count = seller_config.seller_count if seller_config else 1

                prefix_str = 'RINV' if move.move_type == 'out_refund' else 'INV'
                target_prefix = f"{prefix_str}/{count}/"

                if move.name and move.name != '/':
                    if move.name.startswith(f'{prefix_str}/') and not move.name.startswith(target_prefix):
                        move.name = move.name.replace(f'{prefix_str}/', target_prefix, 1)

    def _get_mail_template(self):
        """
        :return: the correct mail template based on the current move type
        """
        return self.env.ref(
            'multi_payment_checkout.email_template_edi_credit_note'
            if all(move.move_type == 'out_refund' for move in self)
            else 'account.email_template_edi_invoice'
        )

    @api.depends('name', 'state')
    def _compute_duplicate_name_warning(self):
        for move in self:
            if move.name and move.name != '/':
                domain = [
                    ('id', '!=', move._origin.id if move._origin else False),
                    ('name', '=', move.name),
                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                    ('company_id', '=', move.company_id.id)
                ]
                if hasattr(move, 'marketplace_seller_id') and move.marketplace_seller_id:
                    domain.append(('marketplace_seller_id', '=', move.marketplace_seller_id.id))

                count = self.search_count(domain)
                move.duplicate_name_warning = count > 0
            else:
                move.duplicate_name_warning = False
