# -*- coding: utf-8 -*-
import logging
from ast import literal_eval
from odoo import models, _

_logger = logging.getLogger(__name__)


class SellerConfirmationPortal(models.TransientModel):
    _inherit = 'seller.resistration.wizard'

    def confirm_customer_as_seller(self):
        """
        Override: when confirming a customer as a seller (admin wizard flow),
        keep the user as a Portal user instead of converting to Internal User.
        """
        try:
            current_user_id = self.user_id
            partner_id = self.partner_id

            if not current_user_id:
                values = {
                    'name': partner_id.name,
                    'login': partner_id.email,
                    'partner_id': partner_id.id,
                }
                IrConfigParam = self.env['ir.config_parameter']
                template_user_id = literal_eval(
                    IrConfigParam.get_param('base.template_portal_user_id', 'False')
                )
                template_user = self.env['res.users'].browse(template_user_id)
                assert template_user.exists(), 'Signup: invalid template user'

                values['active'] = True
                # Copy from the portal template — this inherits Portal group by default;
                current_user_id = template_user.with_context(
                    no_reset_password=True
                ).copy(values)

            wk_valse = {
                "payment_method": [(6, 0, current_user_id.partner_id._set_payment_method())],
                "commission": self.env['ir.default']._get('res.config.settings', 'mp_commission'),
                "location_id": self.env['ir.default']._get(
                    'res.config.settings', 'mp_location_id', company_id=True) or False,
                "warehouse_id": self.env['ir.default']._get(
                    'res.config.settings', 'mp_warehouse_id', company_id=True) or False,
                "auto_product_approve": self.auto_product_approve,
                "seller_payment_limit": self.env['ir.default']._get(
                    'res.config.settings', 'mp_seller_payment_limit'),
                "next_payment_request": self.env['ir.default']._get(
                    'res.config.settings', 'mp_next_payment_request'),
                "auto_approve_qty": self.auto_approve_qty,
                "url_handler": partner_id.id,
                "seller": True,
            }
            current_user_id.partner_id.write(wk_valse)

            draft_seller_group_id = self.env['ir.model.data'].check_object_reference(
                'odoo_marketplace', 'marketplace_draft_seller_group'
            )[1]
            groups_obj = self.env["res.groups"].browse(draft_seller_group_id)
            if groups_obj:
                for group_obj in groups_obj:
                    group_obj.sudo().write({"users": [(4, current_user_id.id, 0)]})

            # Keep seller as PORTAL user
            grp_portal = self.env['ir.model.data']._xmlid_lookup('base.group_portal')[1]
            grp_portal_obj = self.env['res.groups'].browse(grp_portal)
            grp_portal_obj.write({'users': [(4, current_user_id.id)]})

            # Remove from Internal User group if somehow they were in it
            grp_internal = self.env['ir.model.data']._xmlid_lookup('base.group_user')[1]
            grp_internal_obj = self.env['res.groups'].browse(grp_internal)
            grp_internal_obj.write({'users': [(3, current_user_id.id)]})

            if self.auto_approve_seller:
                current_user_id.partner_id.write({'state': 'approved'})

            if not self.user_id:
                current_user_id.action_reset_password()
            current_user_id.notification_on_partner_as_a_seller()

        except Exception as e:
            _logger.warning(
                "Warning !! Not able to create seller as portal user ~ Exception(%r)", e
            )

        return {
            'name': _('Confirmation'),
            'type': 'ir.actions.act_window',
            'res_model': 'seller.resistration.wizard',
            'view_mode': 'form',
            'binding_view_types': 'form',
            'res_id': self.id,
            'view_id': self.env.ref('odoo_marketplace.registration_completed_wizard_form').id,
            'context': {'auto_approve_seller': self.auto_approve_seller},
            'target': 'new',
        }
