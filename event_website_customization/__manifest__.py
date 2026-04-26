# -*- coding: utf-8 -*-
{
    'name': 'Website Event Multi-Location & Map Enhancements',
    'version': '1.0.0',
    'summary': 'Enhances Odoo Events on Website: multiple partners, Google map links, UI changes.',
    'description': """
    Website Event Multi-Location & Map Enhancements
    ===============================================
    Features:
    - Add multiple partner/locations to events.
    - Modify event templates to show multiple addresses.
    - Dynamic Google Maps link per partner.
    - Customize registration/description templates.
    """,
    'category': 'Website/Events',
    'author': '',
    'maintainer': '',
    'website': '',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'event',
        'website_event',
    ],

    'data': [
        # Backend form view to add multiple partners/locations
        'views/view_event_form_inherit_add_partners.xml',

        # Website XML override to show multi-location & map links
        'views/event_website_customization_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
