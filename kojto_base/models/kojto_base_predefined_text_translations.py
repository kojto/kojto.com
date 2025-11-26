from odoo import models, fields


class KojtoBaseTextTranslations(models.Model):
    _name = 'kojto.base.text.translations'
    _description = 'Kojto Base Text Translations'

    base_text_id = fields.Many2one('kojto.base.predefined.texts', string='Base Text', required=True, ondelete='cascade')
    language_id = fields.Selection(lambda self: [(lang.code, lang.name) for lang in self.env['res.lang'].search([])], string='Language', required=True)
    translated_text = fields.Text(string='Translation', required=True)

    _sql_constraints = [
        ('base_text_lang_uniq', 'unique(base_text_id, lang)',
         'A translation for this text and language already exists!')
    ]
