from odoo import models, fields

class KojtoBaseNames(models.Model):
    _name = "kojto.base.names"
    _description = "Kojto Names"
    _rec_name = "name"
    _order = "name desc"

    company_id = fields.Many2one("res.company", string="Names")
    active = fields.Boolean(string="Is Active", default=True)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id )
    name = fields.Char(string="Name")
