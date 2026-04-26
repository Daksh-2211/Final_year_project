{
    "name": "Invoice & Sale QR Payment Links",
    "summary": "Show QR & Button for Online Payment on PDF",
    "description": """
    This module allows you to generate a QR code for the payment link of a sale order.
    It also adds a button to the sale order form view that allows you to generate the QR code and download it as an image file.
    """,
    "category": "Sale/Accounting",
    "author": "BB Logic Inc",
    "version": "18.0.1.0.0",
    "depends": ["sale","account_payment"],
    "data": [
        "data/data.xml",
        "report/account_reports.xml",
        "report/sale_reports.xml",
    ],
    "images": ["static/description/images/banner.png","static/description/images/bb_ss1.png","static/description/images/bb_ss2.png","static/description/images/bb_ss3.png"],
    "installable": True,
    "auto_install": False,
    "application": True,
    "price": "5.00",
    "currency": "USD",
    "license": "LGPL-3",
}