import json
import werkzeug
from odoo import http
from odoo.http import request
from odoo.addons.website_event.controllers.main import WebsiteEventController

# Maps camp slug → (template XML ID, snippet filter XML ID)
CAMP_PAGES = {
    'kros-camps': (
        'taborcata_website_blocks.kros_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_kros',
    ),
    'auo-camps': (
        'taborcata_website_blocks.auo_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_auo',
    ),
    'arval-camps': (
        'taborcata_website_blocks.arval_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_arval',
    ),
    'posam-camps': (
        'taborcata_website_blocks.posam_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_posam',
    ),
    'yanfeng-camps': (
        'taborcata_website_blocks.yanfeng_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_yanfeng',
    ),
    'eset-camps': (
        'taborcata_website_blocks.eset_camps_page',
        'taborcata_website_blocks.website_snippet_filter_b2b_eset',
    ),
}


class B2BCampPage(http.Controller):

    @http.route(
        ['/kros-camps', '/auo-camps', '/arval-camps', '/posam-camps', '/yanfeng-camps', '/eset-camps'],
        type='http', auth='user', website=True
    )
    def b2b_camp_page(self, **kw):
        # Extract the slug from the URL path
        camp_slug = request.httprequest.path.strip('/')

        if camp_slug not in CAMP_PAGES:
            raise werkzeug.exceptions.NotFound()

        # ✅ Access control: check if user's company matches the camp's B2B partner
        user_company = request.env.user.partner_id.commercial_partner_id
        camp_event = request.env['event.event'].sudo().search([
            ('b2b_camp_page', '=', camp_slug),
            ('website_published', '=', True),
        ], limit=1)
        if camp_event and camp_event.b2b_partner_id:
            if user_company != camp_event.b2b_partner_id:
                raise werkzeug.exceptions.NotFound()

        template_id, filter_xml_id = CAMP_PAGES[camp_slug]

        filter_rec = request.env.ref(filter_xml_id, raise_if_not_found=False)
        commercial_partner = request.env.user.partner_id.commercial_partner_id
        website = request.website
        hidden_event_ids = website.event_ids.ids if website.event_ids else []

        values = {
            'filter_id': filter_rec.id if filter_rec else False,
            'partner_id': commercial_partner.id,
            'hidden_event_ids': hidden_event_ids,
            'camp_slug': camp_slug,
        }
        return request.render(template_id, values)

class ContextAwareEventController(WebsiteEventController):
    
    ROUTE_FILTERS = {
        'petrzalka': 'Petržalka',
        'ruzinov': 'Ružinov',
        'lamac': 'Lamač',
        'raca': 'Rača',
        'karlova-ves': 'Karlova Ves',
    }

    @http.route([
        '/events/denny',
        '/events/denny/page/<int:page>',
        '/events/denny/<string:camp_slug>',
        '/events/denny/<string:camp_slug>/page/<int:page>',
        '/events/pobytove',
        '/events/pobytove/page/<int:page>'
    ], type='http', auth="public", website=True, sitemap=False)
    def custom_events(self, camp_slug=None, page=1, **post):
        path = request.httprequest.path
        tags_to_find = []
        
        if '/events/pobytove' in path:
            tags_to_find = ['Pobytový tábor']
        elif '/events/denny' in path:
            tags_to_find = ['Denný tábor']
            if camp_slug:
                if camp_slug not in self.ROUTE_FILTERS:
                    raise werkzeug.exceptions.NotFound()
                tags_to_find.append(self.ROUTE_FILTERS[camp_slug])
        else:
            raise werkzeug.exceptions.NotFound()
            
        tags = request.env['event.tag'].sudo().search([('name', 'in', tags_to_find)])
        tag_ids = tags.ids
        
        if tag_ids:
            existing_tags = []
            if post.get('tags'):
                try:
                    existing_tags = json.loads(post['tags'])
                except Exception:
                    existing_tags = []
            
            all_tags = list(set(existing_tags + tag_ids))
            post['tags'] = json.dumps(all_tags)
            
        # Odoo 18 redirects GET requests with multiple tags to /event to prevent bot spam.
        # We bypass this logic by explicitly setting prevent_redirect to True.
        post['prevent_redirect'] = True
            
        resp = self.events(page=page, **post)
        if hasattr(resp, 'is_qweb') and resp.is_qweb:
            resp.template = 'taborcata_website_blocks.custom_events_page_index'
            camp_name = self.ROUTE_FILTERS.get(camp_slug, 'Denné tábory') if camp_slug else 'Pobytové tábory'
            resp.qcontext['camp_name'] = camp_name
        return resp
