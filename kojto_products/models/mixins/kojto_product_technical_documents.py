# kojto_products/models/mixins/kojto_product_technical_documents.py
from odoo import models, fields, api


class KojtoProductTechnicalDocumentMixin(models.AbstractModel):
    _name = 'kojto.product.technical.document.mixin'
    _description = 'Kojto Product Technical Document Mixin'

    # Technical Document-specific fields
    document_number = fields.Char(string='Document Number', index=True)
    document_file = fields.Binary(string='Document File', attachment=True)
    document_filename = fields.Char(string='Filename')
    document_scale = fields.Char(string='Scale')
    document_format = fields.Selection([
        ('A0', 'A0'),
        ('A1', 'A1'),
        ('A2', 'A2'),
        ('A3', 'A3'),
        ('A4', 'A4'),
        ('custom', 'Custom')
    ], string='Format')
    document_author = fields.Many2one('res.users', string='Author')
    document_type = fields.Selection([
        ('drawing', 'Drawing'),
        ('calculation', 'Calculation'),
        ('method_statement', 'Method Statement'),
        ('manual', 'Manual'),
        ('other', 'Other')
    ], string='Document Type', default='drawing', required=True)
    number_of_pages = fields.Integer(string='Number of Pages', default=1)

