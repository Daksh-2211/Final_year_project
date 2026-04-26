# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class EventEvent(models.Model):
    _inherit = 'event.event'

    is_b2b = fields.Boolean(string="Is B2B/Hidden Event", default=False)
    b2b_partner_id = fields.Many2one('res.partner', string="B2B Client")
    b2b_camp_page = fields.Selection([
        ('kros-camps', 'KROS Camps'),
        ('auo-camps', 'AUO Camps'),
        ('arval-camps', 'Arval Camps'),
        ('posam-camps', 'PosAm Camps'),
        ('yanfeng-camps', 'Yanfeng Camps'),
        ('eset-camps', 'ESET Camps'),
    ], string="B2B Camp Page", help="Assign this event to a specific B2B camp page")
    # b2b_camp_url = fields.Char(
    #     string="B2B Camp Page URL",
    #     compute='_compute_b2b_camp_url',
    #     store=False,
    # )

    # @api.depends('b2b_camp_page')
    # def _compute_b2b_camp_url(self):
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
    #     for rec in self:
    #         if rec.b2b_camp_page:
    #             rec.b2b_camp_url = '%s/%s' % (base_url.rstrip('/'), rec.b2b_camp_page)
    #         else:
    #             rec.b2b_camp_url = False