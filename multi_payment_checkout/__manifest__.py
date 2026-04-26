# -*- coding: utf-8 -*-

{
    "name": "Marketplace Unified Checkout & Seller Subscriptions",
    "version": "18.0.1.0.0",
    "category": "Website",
    "summary": "Unified payment for multi-seller carts with auto-subscription handling and IČO support",
    "description": """
    This module extends the Odoo Marketplace to provide a seamless unified checkout experience.
    
    Key Features:
    * **Unified Checkout:** Allows customers to pay for items from multiple sellers in a single transaction.
    * **Order Splitting:** Automatically splits the Master Order into individual Seller Orders after payment.
    * **Auto-Subscription:** Automatically adds a Seller's specific Membership/Subscription product to the cart when buying their Event tickets.
    * **Subscription Plan Logic:** Ensures Odoo 18 Subscription Plans are correctly applied to split orders.
    * **Payment Linking:** Auto-links the single payment transaction to multiple seller invoices.
    * **Auto-Reconciliation:** Automatically creates invoices and reconciles payments for all sellers immediately.
    * **Slovak Localization:** Adds 'IČO' field to partners and displays it on Invoice reports based on customer language.
    """,
    "depends": [
        "mail",
        "website_sale",
        "website_event_sale",
        "website_event",
        "payment",
        "sale_management",
        "account",
        "odoo_marketplace",
        "marketplace_seller_wise_checkout"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/seller_invoice_sequence_views.xml",
        "views/mail_template_sale_confirmation.xml",
        "views/mail_template_invoice_confirmation.xml",
        "views/cart_button.xml",
        "views/mail_template_inherit.xml",
        "views/report_templates.xml",
        "views/sellerwise_membership_views.xml",
        "views/report_invoice_inherit.xml",
        "views/website_shop_template.xml",
        "views/partner_view_inherit.xml",
        "views/sale_order_line_views.xml",
        "views/account_move_line_views.xml",
        "views/gtm_datalayer_templates.xml",
        "views/gtm_global_tracking_templates.xml",
        "views/seo_verification_template.xml",
        'views/report_invoice.xml',
        'data/mail_template_data.xml',
        'data/unpaid_order_reminder.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'multi_payment_checkout/static/src/js/cart_fix.js',
            'multi_payment_checkout/static/src/css/custom_font.css',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
