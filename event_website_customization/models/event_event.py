# -*- coding: utf-8 -*-

from odoo import _,api, fields, models

class EventEvent(models.Model):
    _inherit = 'event.event'

    address_ids = fields.Many2many(
        'res.partner',
        string='Related Partners',
        help='Partners related to this event'
    )

    def _google_map_link(self, partner=None, zoom=8):
        """Return Google Maps link for the event address or a given partner."""
        self.ensure_one()
        if partner:  # if a partner is explicitly passed
            return partner.sudo().google_map_link(zoom=zoom)
        elif self.address_id:  # fallback to the event's main address
            return self.sudo().address_id.google_map_link(zoom=zoom)
        return None 