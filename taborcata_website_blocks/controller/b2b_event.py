# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL


class WebsiteEventB2BController(http.Controller):
    @http.route(['/event_b2b', '/event_b2b/page/<int:page>'], type='http', auth="user", website=True)
    def events_b2b(self, page=1, **kwargs):
        Event = request.env['event.event']
        partner = request.env.user.partner_id.commercial_partner_id

        # 1. Search Params
        searches = {
            'search': kwargs.get('search', ''),
            'date': kwargs.get('date', 'all'),
        }

        # 2. Setup QueryURL (Ensures links stay on /event_b2b)
        keep = QueryURL('/event_b2b', **searches)

        # 3. Build Domain
        domain = [('website_published', '=', True), ('b2b_partner_id', '=', partner.id)]

        if searches['search']:
            domain.append(('name', 'ilike', searches['search']))

        if searches['date'] == 'upcoming':
            domain.append(('date_begin', '>', fields.Datetime.now()))

        # 4. Fetch Events
        all_events = Event.search(domain, order="date_begin asc")

        # 5. Prepare Counts for Date Filter
        total_b2b = Event.search_count([('b2b_partner_id', '=', partner.id), ('website_published', '=', True)])
        upcoming_b2b = Event.search_count([
            ('b2b_partner_id', '=', partner.id),
            ('website_published', '=', True),
            ('date_begin', '>', fields.Datetime.now())
        ])

        # 6. Pager & Rendering
        pager = request.website.pager(url="/event_b2b", total=len(all_events), page=page, step=9, url_args=searches)

        values = {
            'event_ids': all_events[(page - 1) * 9: page * 9],
            'pager': pager,
            'searches': searches,
            'keep': keep,
            'dates_list': [
                {'id': 'all', 'name': 'All Events', 'count': total_b2b},
                {'id': 'upcoming', 'name': 'Upcoming', 'count': upcoming_b2b}
            ],
            'search_count': len(all_events),
        }
        return request.render("taborcata_website_blocks.event_b2b_index", values)
