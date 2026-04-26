from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _apply_taxes_to_price(self, price, currency, product_taxes, mapped_taxes, product, website=None):
        result = super()._apply_taxes_to_price(
            price, currency, product_taxes, mapped_taxes,
            product, website=website
        )

        if mapped_taxes:
            tax_data = mapped_taxes.compute_all(
                price,
                currency=currency,
                quantity=1.0,
                product=product,
            )
            return tax_data['total_included']

        return result