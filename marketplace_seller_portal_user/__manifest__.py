{
    'name': 'Marketplace Seller Portal User',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Sets newly registered sellers as Portal users instead of Internal users.',
    'description': """
        This module overrides the seller registration logic in odoo_marketplace so that
        when a seller is created (either via website self-signup or the admin wizard),
        the corresponding res.users record is assigned the Portal user type instead of
        the default Internal user type.
    """,
    'depends': ['odoo_marketplace'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
