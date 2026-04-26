{
    "name": "Pohoda Invoice Export",
    "version": "18.0.1.0",
    "summary": "Export invoices to Pohoda XML format",
    "author": "Your Company",
    "category": "Accounting",
    "depends": ["account"],
    "data": [
        'data/ir_cron_data.xml',

        "security/ir.model.access.csv",
        "views/pohoda_export_views.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'pohoda_invoice_export/static/src/js/pohoda_download.js',
        ],
    },
    "installable": True,
    "application": False,
}
