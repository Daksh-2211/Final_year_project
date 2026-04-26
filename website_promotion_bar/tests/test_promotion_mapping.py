# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo.tests.common import TransactionCase

class TestPromotionMapping(TransactionCase):
    def setUp(self):
        super(TestPromotionMapping, self).setUp()
        page_id = self.env["ir.ui.view"].search([('key','=','website.homepage')])
        self.promotion_rec1 = self.env["promotion.mapping"].create({
            'page_id': page_id.id,
            'position': 'top',
            'visibility': 'public',
            'date_start': '2019-06-01',
            'content': """Diwali Dhamaka Offer!!! Grab It!!!""",
        })

        self.promotion_rec2 = self.env["promotion.mapping"].create({
            'page_id': page_id.id,
            'position': 'top',
            'visibility': 'public',
            'date_start': '2019-06-01',
            'content': """Grand Sale!!! Hurry Up!!!""",
        })

        self.promotion_rec3 = self.env["promotion.mapping"].create({
            'page_id': page_id.id,
            'position': 'top',
            'visibility': 'public',
            'date_start': '2019-06-01',
            'content': """Big Sale on Local Variety!! Don't Miss!!""",
            'is_multi_promotion': True,
            'promotion_id': self.promotion_rec2.id,
        })

    def test_allow_and_successive(self):
        self.assertTrue(not self.promotion_rec1.is_multi_promotion)

    def test_successive_for_multi_promotion(self):
        self.assertTrue(not self.promotion_rec2.is_multi_promotion)
        self.assertTrue(self.promotion_rec2.promotion_ids)

    def test_publish_on_creation(self):
        self.assertTrue(not self.promotion_rec1.publish)
        self.assertTrue(not self.promotion_rec2.publish)
        self.assertTrue(not self.promotion_rec3.publish)

    def test_publish_all_records(self):
        self.promotion_rec1.promotion_publish_button()
        self.assertTrue(self.promotion_rec1.publish)
        self.promotion_rec2.promotion_publish_button()
        self.assertTrue(not self.promotion_rec2.publish)
        self.promotion_rec1.promotion_publish_button()
        self.promotion_rec2.promotion_publish_button()
        self.promotion_rec3.promotion_publish_button()
        self.assertTrue(not self.promotion_rec1.publish)
        self.assertTrue(self.promotion_rec2.publish)
        self.assertTrue(self.promotion_rec3.publish)

    def test_unlink_records(self):
        self.promotion_rec2.unlink()
        self.assertTrue(not self.promotion_rec3.publish)
        self.assertTrue(not self.promotion_rec3.view_id.active)
        self.assertTrue(not self.promotion_rec3.is_multi_promotion)
        self.assertTrue(not self.promotion_rec3.promotion_id)

    def test_multi_promotions(self):
        self.promotion_rec2.promotion_publish_button()
        self.promotion_rec3.promotion_publish_button()
        self.promotion_rec2.write({
            'is_multi_promotion': True,
            'promotion_id': self.promotion_rec1.id,
        })
        self.assertTrue(self.promotion_rec1.promotion_ids)
        self.assertTrue(not self.promotion_rec2.promotion_ids)
        self.assertTrue(not self.promotion_rec3.promotion_id)
        self.assertTrue(not self.promotion_rec3.publish)
        self.assertTrue(not self.promotion_rec3.view_id.active)

    def test_publish_on_position_change(self):
        self.promotion_rec1.promotion_publish_button()
        self.promotion_rec1.write({'position': 'left'})
        self.assertTrue(not self.promotion_rec1.publish)
        self.assertTrue(not self.promotion_rec1.view_id.active)
