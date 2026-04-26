{
    "name": "Taborcata Website Blocks",
    "version": "18.0.0.1",
    "category": "Website",
    "summary": "Custom mega menu block for Taborcata",
    "depends": [
        "web_editor", "hidden_products"
    ],
    "data": [
        'data/event_filter_data.xml',
        "views/menu_data.xml",
        "views/event_template.xml",
        'views/event_views.xml',
        'views/kros_camps_page.xml',
        'views/auo_camps_page.xml',
        'views/arval_camps_page.xml',
        'views/posam_camps_page.xml',
        'views/yanfeng_camps_page.xml',
        'views/eset_camps_page.xml',
        'views/event_b2b_templates.xml',
        'views/template.xml',
        'views/global_cta.xml',
        'views/custom_events_page.xml',
        'views/website_event_filters.xml',
    ],
    "assets": {
        'web.assets_frontend': [
            'taborcata_website_blocks/static/src/css/mega_menu.css',
            'taborcata_website_blocks/static/src/js/events_see_all.js',
            'taborcata_website_blocks/static/src/js/mega_menu_click.js',
            'taborcata_website_blocks/static/src/js/global_cta.js',
            'taborcata_website_blocks/static/src/css/event_template.css',
            'taborcata_website_blocks/static/src/scss/global_cta.scss',
            'taborcata_website_blocks/static/src/xml/website_sale_stock_translation.xml'
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
