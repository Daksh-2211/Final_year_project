import logging
import base64
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def action_create_payments(self):
        res = super(AccountPaymentRegister, self).action_create_payments()
        invoices = self.line_ids.move_id

        for inv in invoices:
            tx = self.env['payment.transaction'].sudo().search([
                ('sale_order_ids', 'in', inv.line_ids.sale_line_ids.order_id.ids),
                ('state', '!=', 'done')
            ], limit=1)

            if not tx and self.communication:
                tx = self.env['payment.transaction'].sudo().search([
                    ('reference', '=', self.communication)
                ], limit=1)

            if tx and tx.state != 'done':
                _logger.info(f"Setting Transaction {tx.reference} to Done.")
                tx.write({'state': 'done'})  # Marks as Confirmed

            # Only send confirmation emails for customer invoices,
            # NOT for vendor bills (in_invoice) or other move types.
            if inv.move_type == 'out_invoice':
                self._force_send_paid_invoice_email(inv)
            else:
                _logger.info(
                    f"Skipping invoice email for {inv.name} (move_type={inv.move_type}) — "
                    f"not a customer invoice."
                )

        return res

    def _force_send_paid_invoice_email(self, inv):
        try:
            template = self.env.ref('multi_payment_checkout.taborcata_invoice_confirmation', raise_if_not_found=False)
            if template:
                pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                                     'account.account_invoices', res_ids=inv.id)

                attachment = self.env['ir.attachment'].sudo().create({
                    'name': f"{inv.name}.pdf".replace('/', '_'),
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'account.move',
                    'res_id': inv.id,
                    'mimetype': 'application/pdf',
                })

                template.send_mail(inv.id, force_send=True,email_values = {'attachment_ids': [(4, attachment.id)],'email_from': 'taborcata@taborcata.sk'})
                _logger.info(f"Paid Invoice PDF sent for {inv.name}")
        except Exception as e:
            _logger.error(f"Email failure: {str(e)}")