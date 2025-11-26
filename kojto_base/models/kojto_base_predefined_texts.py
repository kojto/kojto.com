from odoo import models, fields


class KojtoBasePredefinedTexts(models.Model):
    _name = 'kojto.base.predefined.texts'
    _description = 'Kojto Base Predefined Texts'
    _sql_constraints = [('name_type_uniq', 'unique(name, text_type)', 'A text with this name and type already exists!')]

    name = fields.Char(string='Name', required=True)
    text_type = fields.Selection([
        ('offer_pre_content_text', 'Offer Pre-Content Text'),
        ('offer_post_content_text', 'Offer Post-Content Text'),
        ('invoice_text', 'Invoice Text'),
        ('contract_text', 'Contract Text'),
        ('delivery_text', 'Delivery Text'),
        ('ut_control_result', 'UT Control Result'),
    ], string='Text Type', required=True)

    translation_ids = fields.One2many('kojto.base.text.translations', 'base_text_id', string='Translations')
