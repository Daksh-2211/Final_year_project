from odoo.addons.sale.controllers.product_configurator import SaleProductConfiguratorController
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request, route
from odoo import http
from odoo.addons.website.controllers.main import Website
import logging
_logger = logging.getLogger(__name__)


class WebsiteAutocompleteInherit(Website):

    @http.route('/website/snippet/autocomplete', type='json', auth='public', website=True, readonly=True)
    def autocomplete(self, **kwargs):
        res = super(WebsiteAutocompleteInherit, self).autocomplete(**kwargs)
        if not res or 'results' not in res:
            return res
        website = request.website
        hidden_events = website.event_ids

        if not hidden_events:
            return res

        hidden_ids = [str(event.id) for event in hidden_events]
        hidden_names = [event.name for event in hidden_events]
        filtered_results = []
        for item in res['results']:
            url = item.get('website_url') or item.get('url') or item.get('link') or ''
            name = item.get('name', '')
            should_hide = False

            if '/event/' in url:
                for event_id in hidden_ids:
                    if url.endswith(f"-{event_id}"):
                        should_hide = True
                        break

            if not should_hide and name in hidden_names:
                if '/event/' in url:
                    should_hide = True

            if not should_hide:
                filtered_results.append(item)

        res['results'] = filtered_results
        return res

class WebsiteSaleInherit(SaleProductConfiguratorController,WebsiteSale):

    @route(
        route='/website_sale/product_configurator/get_values',
        type='json',
        auth='public',
        website=True,
    )
    def website_sale_product_configurator_get_values(self, *args, **kwargs):
        self._populate_currency_and_pricelist(kwargs)
        res = super().sale_product_configurator_get_values(*args, **kwargs)
        if res.get('optional_products'):
            website_products = set(product.id for product in request.env['website'].get_current_website().product_ids)
            res['optional_products'] = [item for item in res['optional_products'] if item['product_tmpl_id'] not in website_products]
        return res
