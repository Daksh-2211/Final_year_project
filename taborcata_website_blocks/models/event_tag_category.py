from odoo import models, fields, api


class EventTag(models.Model):
    _inherit = 'event.tag'

    is_b2b = fields.Boolean(
        string="B2B",
        compute='_compute_is_b2b',
        store=False,
        help="True if the tag is associated with any hidden event with a B2B client."
    )

    def _compute_is_b2b(self):
        """Recomputes on every access. Checks if any event for this tag is hidden and has B2B client."""
        # Collect all hidden event IDs from all websites
        all_hidden_ids = self.env['website'].sudo().search([]).mapped('event_ids').ids
        EventEvent = self.env['event.event'].sudo()

        for tag in self:
            # A tag is B2B if ANY event using it is in the hidden list AND has a B2B client set
            tag.is_b2b = bool(EventEvent.search_count([
                ('tag_ids', 'in', tag.id),
                ('id', 'in', all_hidden_ids),
                ('b2b_partner_id', '!=', False)
            ]))


class EventTagCategory(models.Model):
    _inherit = 'event.tag.category'

    is_b2b = fields.Boolean(
        string="B2B",
        compute='_compute_is_b2b',
        store=False,
        help="True if any tag under this category is B2B."
    )

    def _compute_is_b2b(self):
        """A category is B2B if it contains at least one B2B tag."""
        for category in self:
            category.is_b2b = any(tag.is_b2b for tag in category.tag_ids)
