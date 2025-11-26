from odoo import models, fields

class KojtoBaseIncoterms(models.Model):
    _name = "kojto.base.incoterms"
    _description = "Kojto Base Incoterms"
    _rec_name = "name"
    _order = "name desc"

    abbreviation = fields.Char("Abbreviation")
    description = fields.Text("Description")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    name = fields.Char("Name")
