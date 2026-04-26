# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from odoo import models, fields, api, _


class Website(models.Model):
    _inherit = 'website'

    product_ids = fields.Many2many('product.template', 'product_hide_web', 'website_id', 'product_id',string="Hidden Products")
    event_ids = fields.Many2many('event.event', 'event_hide_web', 'website_id', 'event_id', string="Hidden Events")

    # 1. HIDE FROM SHOP PAGE
    @api.model
    def sale_product_domain(self):
        domain = super(Website, self).sale_product_domain()
        if self.product_ids:
            domain += [('id', 'not in', self.product_ids.ids)]
        return domain

    # 2. HIDE FROM EVENT PAGE
    def event_domain(self):
        domain = super(Website, self).event_domain()
        if self.event_ids:
            domain += [('id', 'not in', self.event_ids.ids)]
        return domain

    def write(self, vals):
        res = super(Website, self).write(vals)
        if 'event_ids' in vals:
            if self.env.context.get('skip_ticket_sync'):
                return res

            for website in self:
                tickets = self.env['event.event.ticket'].sudo().search([('event_id', 'in', website.event_ids.ids)])
                ticket_products = tickets.mapped('product_id.product_tmpl_id')
                current_hidden = website.product_ids
                missing_products = ticket_products - current_hidden
                if missing_products:
                    website.with_context(skip_ticket_sync=True).write({
                        'product_ids': [(4, product.id) for product in missing_products]
                    })
        return res


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = "Website Hidden Content Settings"

    product_ids = fields.Many2many("product.template", related="website_id.product_ids", string="Hidden Products",readonly=False)
    event_ids = fields.Many2many("event.event", related="website_id.event_ids", string="Hidden Events", readonly=False)

    @api.onchange('event_ids')
    def _onchange_event_ids(self):
        if self.event_ids:
            tickets = self.env['event.event.ticket'].search([('event_id', 'in', self.event_ids.ids)])
            ticket_products = tickets.mapped('product_id.product_tmpl_id')
            self.product_ids = self.product_ids | ticket_products


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    @api.model
    def _get_products(self, mode, **kwargs):
        res = super(WebsiteSnippetFilter, self)._get_products(mode, **kwargs)
        website = self.env['website'].get_current_website()
        hidden_products = set(website.product_ids.ids)
        # Filter the result list
        return [p for p in res if p.get('product_template_id') not in hidden_products]

    @api.model
    def _get_events(self, mode, **kwargs):
        res = super(WebsiteSnippetFilter, self)._get_events(mode, **kwargs)
        website = self.env['website'].get_current_website()
        hidden_events = set(website.event_ids.ids)
        return [e for e in res if e.get('id') not in hidden_events]

