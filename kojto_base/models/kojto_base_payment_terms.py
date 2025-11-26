from odoo import models, fields

class KojtoBasePaymentTerms(models.Model):
    _name = "kojto.base.payment.terms"
    _description = "Kojto Base Payment Terms"
    _rec_name = "name"
    _order = "name desc"

    abbreviation = fields.Char(string="Abbreviation")
    description = fields.Text("Description")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    name = fields.Char(string="Name")
