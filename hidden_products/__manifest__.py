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
  "name"                 :  "Website Hidden Product",
  "summary"              :  """Provide Product hide options as the same time  Product available for direct  sale on website.""",
  "category"             :  "Website",
  "version"              :  "1.0.0",
  "sequence"             :  0,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "maintainer"           :  "Prakash Kumar",
  "website"              :  "https://store.webkul.com/Odoo-Website-Hidden-Product.html",
  "description"          :  """Hide Product from website by using hide options as the same time  Product available for direct  sale on website.""",
  "live_test_url"        :  "http://odoodemo.webkul.com/?module=hidden_products",
  "depends"              :  [
                             'website_sale','website','website_event'
                            #  'website_sale_product_configurator',
                            #  'sale_product_configurator',
                            ],
  "data"                 :  [
                             'security/ir.model.access.csv',
                             'views/views.xml',
                             'views/template.xml',
                            ],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "price"                :  20.0,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
}
