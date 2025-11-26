# kojto_products/models/kojto_product_dwg_viewport_boq_lines.py
from odoo import models, fields, api


class KojtoProductBoqLine(models.Model):
    _name = 'kojto.product.boq.line'
    _description = 'Kojto Product BOQ Line'
    _rec_name = 'item_description'
    _order = 'sequence, id'

    # Sequence for ordering
    sequence = fields.Integer(string='Sequence', default=10)

    # Relation to viewport
    viewport_id = fields.Many2one(
        'kojto.product.dwg.file.viewport',
        string='Viewport',
        required=True,
        ondelete='cascade',
        index=True
    )

    # BOQ line details
    item_number = fields.Char(string='Item Number', index=True)
    item_description = fields.Text(string='Description', required=True)
    item_code = fields.Char(string='Item Code')

    # Quantities
    quantity = fields.Float(string='Quantity', digits='Product Unit of Measure', default=1.0)
    unit_id = fields.Many2one('kojto.base.units', string='Unit')

    # Dimensions (optional, useful for construction BOQ)
    length = fields.Float(string='Length')
    width = fields.Float(string='Width')
    height = fields.Float(string='Height')
    area = fields.Float(string='Area', compute='_compute_area', store=True)
    volume = fields.Float(string='Volume', compute='_compute_volume', store=True)

    # Pricing (optional)
    unit_price = fields.Float(string='Unit Price', digits='Product Price')
    total_price = fields.Float(string='Total Price', compute='_compute_total_price', store=True)

    # Additional metadata
    material = fields.Char(string='Material')
    specification = fields.Text(string='Specification')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)

    @api.depends('length', 'width')
    def _compute_area(self):
        for record in self:
            if record.length and record.width:
                record.area = record.length * record.width
            else:
                record.area = 0.0

    @api.depends('length', 'width', 'height')
    def _compute_volume(self):
        for record in self:
            if record.length and record.width and record.height:
                record.volume = record.length * record.width * record.height
            else:
                record.volume = 0.0

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price


