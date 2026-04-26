# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def copy(self, default=None):
        """
        Override: when a seller is registered via website signup ,
        ensure the user type is Portal instead of Internal User.
        """
        user_obj = super(ResUsers, self).copy(default=default)

        if self._context.get('is_seller', False):
            portal_group = self.env.ref('base.group_portal')
            internal_group = self.env.ref('base.group_user')
            user_obj.sudo().write({
                'groups_id': [(3, internal_group.id), (4, portal_group.id)],
            })
            _logger.info(
                "marketplace_seller_portal_user: seller user %s set to Portal user type.",
                user_obj.name,
            )

        return user_obj
