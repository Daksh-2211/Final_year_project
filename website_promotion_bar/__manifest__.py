# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "Website Promotion Bar",
  "summary"              :  """Place announcements and promotion Bars on the web page of your Odoo website. Show Offers and sales and much more.""",
  "category"             :  "Website",
  "version"              :  "1.0.0",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/odoo-website-promotion-bar.html",
  "description"          :  """Promotional bar on website page
Announcement Bar on the odoo website
Odoo website announcement bar
Website announcement messages
Promotion messages on the webpage
Announcements on home page
Add event announcement on webpages
Display sale promotion on webpage
Announcement bar
Website Promotional wizard
Show offers on website
Announcement space on top of website""",
  "live_test_url"        :  "http://odoodemo.webkul.com/?module=website_promotion_bar&custom_url=/",
  "depends"              :  ['website_webkul_addons'],
  "data"                 :  [
                             'security/ir.model.access.csv',
                             'wizard/multi_promotion_wizard_views.xml',
                             'views/promotion_mapping.xml',
                             'views/promotion_config_settings_view.xml',
                             'data/promotion_config_data.xml',
                            ],
  "demo"                 :  ['data/promotion_mapping_demo.xml'],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  69,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
  "assets"               :  {
    'web.assets_frontend':  [
                             'website_promotion_bar/static/src/js/promotion_mapping.js',
                             'website_promotion_bar/static/src/scss/promotion_mapping.scss',
                            ],
                            },
}
