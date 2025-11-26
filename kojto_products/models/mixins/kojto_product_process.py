# kojto_products/models/mixins/kojto_product_process.py
from odoo import models, fields, api


class KojtoProductProcessMixin(models.AbstractModel):
    _name = 'kojto.product.process.mixin'
    _description = 'Kojto Product Process Mixin'

    # Process-specific fields
    process_code = fields.Char(string='Process Code', index=True)
    process_category = fields.Selection([
        ('manufacturing', 'Manufacturing'),
        ('assembly', 'Assembly'),
        ('welding', 'Welding'),
        ('painting', 'Painting'),
        ('machining', 'Machining'),
        ('inspection', 'Inspection'),
        ('packaging', 'Packaging'),
        ('logistics', 'Logistics'),
        ('other', 'Other')
    ], string='Process Category', default='manufacturing')

