{
    'name': 'Sale Order Notes Display',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Display Order Notes on Sales Order and Invoice',
    'description': """
        This module displays the customer order note prominently on:
        - Sales Order form view
        - Sales Order PDF report
        - Invoice (account.move) form view
        - Invoice PDF report
    """,
    'author': 'Custom',
    'depends': ['sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/sale_order_report.xml',
        'report/account_invoice_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
