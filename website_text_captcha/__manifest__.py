{
    "name": "Website Text CAPTCHA",
    "version": "18.0.1.0.0",
    "category": "Website",
    "summary": "Simple text-based CAPTCHA for website forms",
    "depends": ["website","website_crm"],
    "data": [
    ],
    'assets': {
        'web.assets_frontend': [
            'website_text_captcha/static/src/css/captcha.css',
            "website_text_captcha/static/src/js/captcha_insert.js",
        ],
    },
    "external_dependencies": {
        "python": ["captcha"],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
