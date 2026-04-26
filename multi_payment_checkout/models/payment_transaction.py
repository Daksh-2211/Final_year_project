import logging
from odoo import models, fields
from odoo.http import request
import base64

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _post_process(self):
        super()._post_process()

        for tx in self:
            master_orders = tx.sale_order_ids.filtered('is_combined_payment_order')
            normal_orders = tx.sale_order_ids.filtered(lambda o: not o.is_combined_payment_order and o.website_id)
            if master_orders and tx.state in ['done', 'authorized']:
                _logger.info(f"Processing Combined Order Payment: {tx.reference}")
                payment = tx.payment_id

                for master_so in master_orders:
                    for seller_so in master_so.linked_seller_order_ids:
                        try:
                            # Link Transaction to the Split Order
                            # This ensures Odoo knows this payment belongs here!
                            tx.write({'sale_order_ids': [(4, seller_so.id)]})

                            if seller_so.partner_id != master_so.partner_id:
                                seller_so.sudo().write({
                                    'partner_id': master_so.partner_id.id,
                                    'partner_invoice_id': master_so.partner_invoice_id.id,
                                    'partner_shipping_id': master_so.partner_shipping_id.id,
                                })

                            if not seller_so.marketplace_seller_id:
                                for line in seller_so.order_line:
                                    if line.product_id.marketplace_seller_id:
                                        _logger.info(
                                            f"Auto-assigning Seller {line.product_id.marketplace_seller_id.name}")
                                        seller_so.sudo().write({
                                            'marketplace_seller_id': line.product_id.marketplace_seller_id.id
                                        })
                                        break

                            if seller_so.state in ['draft', 'sent']:
                                seller_so.action_confirm()

                                self._force_send_event_registration_mail(seller_so)

                                template = self.sudo().env.ref('multi_payment_checkout.taborcata_sale_confirmation',
                                                           raise_if_not_found=False)
                                if template:
                                    template.send_mail(seller_so.id, force_send=True,email_values={'email_from': 'taborcata@taborcata.sk'})
                                    _logger.info(f"Sent Custom Slovak Mail for {seller_so.name}")
                                else:
                                    _logger.warning(f"Template taborcata_sale_confirmation not found for {seller_so.name}")

                            if not seller_so.invoice_ids:
                                self._auto_invoice_and_reconcile(seller_so, payment)

                        except Exception as e:
                            _logger.error(f"CRITICAL ERROR processing Seller Order {seller_so.name}: {str(e)}")

                    # Reset and Cancel Invoices before Cancelling Master Order
                    try:
                        for inv in master_so.invoice_ids:
                            if inv.state == 'posted':
                                inv.button_draft()
                            if inv.state != 'cancel':
                                inv.button_cancel()

                        master_so._action_cancel()
                    except Exception as e:
                        _logger.error(f"Error cancelling Master Order {master_so.name}: {str(e)}")

            if normal_orders and tx.state in ['done', 'authorized']:
                _logger.info(f"Processing Single Order: {tx.reference}")
                payment = tx.payment_id
                for so in normal_orders:
                    try:
                        if not so.marketplace_seller_id:
                            for line in so.order_line:
                                if line.product_id.marketplace_seller_id:
                                    so.sudo().write({'marketplace_seller_id': line.product_id.marketplace_seller_id.id})
                                    break

                        if so.state in ['draft', 'sent']:
                            so.action_confirm()
                            self._force_send_event_registration_mail(so)

                            template = self.sudo().env.ref('multi_payment_checkout.taborcata_sale_confirmation',
                                                       raise_if_not_found=False)
                            if template:
                                template.send_mail(so.id, force_send=True,email_values={'email_from': 'taborcata@taborcata.sk'})
                                _logger.info(f"Sent Custom Slovak Mail for Single Order {so.name}")

                        if not so.invoice_ids:
                            self._auto_invoice_and_reconcile(so, payment)

                    except Exception as e:
                        _logger.error(f"Error processing standard order {so.name}: {str(e)}")

    def _create_payment(self, **extra_create_values):
        for tx in self:
            journal = tx.provider_id.journal_id

            if not journal:
                _logger.warning(f"No journal found for provider {tx.provider_id.name}")
                continue
            payment_method_line = journal.inbound_payment_method_line_ids[:1]

            if payment_method_line and 'payment_method_line_id' not in extra_create_values:
                extra_create_values['payment_method_line_id'] = payment_method_line.id
                extra_create_values['journal_id'] = journal.id

        return super()._create_payment(**extra_create_values)

    def _auto_invoice_and_reconcile(self, sale_order, payment):
        invoices = sale_order._create_invoices()
        for inv in invoices:
            if inv.state == 'draft':
                inv.write({
                    'delivery_date': fields.Date.context_today(self),
                    'show_delivery_date': True
                })
                inv.action_post()
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

                        # Use send_mail with email_values to attach the PDF
                        template.send_mail(inv.id,
                                           force_send=True,
                                           email_values={'attachment_ids': [(4, attachment.id)],'email_from': 'taborcata@taborcata.sk'})
                        _logger.info(f"Invoice Mail with PDF sent for: {inv.name}")
                except Exception as e:
                    _logger.error(f"Failed to send invoice email for {inv.name}: {str(e)}")

            # Auto-Reconcile
            if payment and payment.move_id:
                receivable_line = payment.move_id.line_ids.filtered(
                    lambda l: l.account_type == 'asset_receivable' and not l.reconciled
                )
                if receivable_line:
                    try:
                        inv.js_assign_outstanding_line(receivable_line.id)
                        _logger.info(f"Successfully reconciled invoice {inv.name}")
                    except Exception as e:
                        _logger.warning(f"Could not auto-reconcile invoice {inv.name}: {str(e)}")

    def _force_send_event_registration_mail(self, sale_order):
        registrations = self.env['event.registration'].sudo().search([
            ('sale_order_id', '=', sale_order.id),
            ('state', 'in', ['open', 'done'])
        ])

        for reg in registrations:
            recipient_email = reg.email or reg.partner_id.email
            if not recipient_email:
                _logger.warning(f"No email for registration {reg.name}, skipping.")
                continue

            attachments = []
            try:
                report_template = 'event.action_report_event_registration_full_page_ticket'
                pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_template, res_ids=reg.id)

                attachment = self.env['ir.attachment'].sudo().create({
                    'name': f"Ticket_{reg.name}.pdf".replace('/', '_'),
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'event.registration',
                    'res_id': reg.id,
                    'mimetype': 'application/pdf',
                })
                attachments.append(attachment.id)
            except Exception as e:
                _logger.error(f"Could not generate ticket PDF for {reg.name}: {str(e)}")

            event = reg.event_id
            mail_schedulers = event.event_mail_ids.filtered(
                lambda m: m.interval_unit == 'now' and m.notification_type == 'mail'
            )

            if mail_schedulers:
                for scheduler in mail_schedulers:
                    template = scheduler.template_ref
                    if template:
                        template.send_mail(
                            reg.id,
                            force_send=True,
                            email_values={
                                'email_from': 'taborcata@taborcata.sk',
                                'email_to': recipient_email,
                                'attachment_ids': [(4, aid) for aid in attachments]
                            }
                        )
                        _logger.info(f"SUCCESS: Sent {template.name} with Ticket to {recipient_email}")