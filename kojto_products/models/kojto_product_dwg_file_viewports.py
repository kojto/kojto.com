# kojto_products/models/kojto_product_dwg_file_viewports.py
from odoo import models, fields, api


class KojtoProductDwgFileViewport(models.Model):
    _name = 'kojto.product.dwg.file.viewport'
    _description = 'Kojto Product DWG File Viewport'
    _rec_name = 'name'

    name = fields.Char(string='Viewport Name', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')

    # Viewport image attachment
    viewport_image = fields.Many2one('ir.attachment', string='Viewport Image', required=True, ondelete='cascade')

    # Relation to DWG File
    dwg_file_id = fields.Many2one('kojto.product.dwg.file', string='DWG File', required=True, ondelete='cascade', index=True)

    # Viewport details
    scale = fields.Char(string='Scale')

    # Dimensions and positioning
    x_position = fields.Float(string='X Position')
    y_position = fields.Float(string='Y Position')
    width = fields.Float(string='Width')
    height = fields.Float(string='Height')

    # Additional metadata
    notes = fields.Text(string='Notes')
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)

    # BOQ Lines relation
    boq_line_ids = fields.One2many('kojto.product.boq.line', 'viewport_id', string='BOQ Lines')

