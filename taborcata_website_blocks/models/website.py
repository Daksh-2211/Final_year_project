from odoo import models, fields, api, _
from odoo.http import request, route
from odoo.osv import expression


class Website(models.Model):
    _inherit = 'website'

    def event_domain(self):
        domain = super().event_domain()
        path = request.httprequest.path

        if path.startswith('/event_b2b'):
            domain.append(('is_b2b', '=', True))
        elif path.startswith('/event'):
            domain.append(('is_b2b', '=', False))
        if self.event_ids:
            domain.append(('id', 'not in', self.event_ids.ids))
        return domain


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    # Map of filter XML IDs to their camp page slugs
    B2B_CAMP_FILTERS = {
        'taborcata_website_blocks.website_snippet_filter_b2b_kros': 'kros-camps',
        'taborcata_website_blocks.website_snippet_filter_b2b_auo': 'auo-camps',
        'taborcata_website_blocks.website_snippet_filter_b2b_arval': 'arval-camps',
        'taborcata_website_blocks.website_snippet_filter_b2b_posam': 'posam-camps',
        'taborcata_website_blocks.website_snippet_filter_b2b_yanfeng': 'yanfeng-camps',
        'taborcata_website_blocks.website_snippet_filter_b2b_eset': 'eset-camps',
    }

    def _prepare_values(self, limit=None, search_domain=None):
        """Inject dynamic B2B partner + hidden events + camp page domain."""
        for filter_xml_id, camp_slug in self.B2B_CAMP_FILTERS.items():
            b2b_filter = self.env.ref(filter_xml_id, raise_if_not_found=False)
            if b2b_filter and self.id == b2b_filter.id:
                extra_domain = []

                # ✅ Filter by current user's company (commercial partner)
                partner = request.env.user.partner_id.commercial_partner_id
                if partner:
                    extra_domain.append(('b2b_partner_id', '=', partner.id))

                # ✅ Only show events from hidden events list
                website = self.env['website'].get_current_website()
                if website and website.event_ids:
                    extra_domain.append(('id', 'in', website.event_ids.ids))

                # ✅ Only show events assigned to this camp page
                extra_domain.append(('b2b_camp_page', '=', camp_slug))

                if extra_domain:
                    search_domain = expression.AND([search_domain, extra_domain]) if search_domain else extra_domain
                break

        return super()._prepare_values(limit=limit, search_domain=search_domain)
