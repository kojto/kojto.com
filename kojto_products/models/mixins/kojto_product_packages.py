# kojto_products/models/mixins/kojto_product_packages.py
from odoo import models, fields, api


class KojtoProductPackagesMixin(models.AbstractModel):
    _name = 'kojto.product.packages.mixin'
    _description = 'Kojto Product Packages Mixin'

    # Package-specific fields
    package_name = fields.Char(string='Package Name', index=True)
    package_description = fields.Text(string='Package Description')
    package_type = fields.Selection([('submission', 'Submission Package'), ('workshop', 'Workshop Package'), ('other', 'Other')], string='Package Type', default='workshop')

