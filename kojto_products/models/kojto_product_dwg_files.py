# kojto_products/models/kojto_product_dwg_files.py
from odoo import models, fields, api


class KojtoProductDwgFile(models.Model):
    _name = 'kojto.product.dwg.file'
    _description = 'Kojto Product DWG File'
    _rec_name = 'name'

    name = fields.Char(string='File Name', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')

    # File attachment
    dwg_file = fields.Many2one('ir.attachment', string='DWG File', required=True, ondelete='cascade')

    # Metadata
    dwg_version = fields.Char(string='DWG Version')
    file_size = fields.Integer(string='File Size (bytes)', compute='_compute_file_size', store=True)
    upload_date = fields.Datetime(string='Upload Date', default=fields.Datetime.now)

    # Relations
    viewport_ids = fields.One2many('kojto.product.dwg.file.viewport', 'dwg_file_id', string='Viewports')
    viewport_count = fields.Integer(string='Viewport Count', compute='_compute_viewport_count', store=True)

    # Technical details
    drawing_number = fields.Char(string='Drawing Number', index=True)
    revision = fields.Char(string='Revision')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)

    @api.depends('dwg_file', 'dwg_file.file_size')
    def _compute_file_size(self):
        for record in self:
            if record.dwg_file:
                record.file_size = record.dwg_file.file_size
            else:
                record.file_size = 0

    @api.depends('viewport_ids')
    def _compute_viewport_count(self):
        for record in self:
            record.viewport_count = len(record.viewport_ids)

