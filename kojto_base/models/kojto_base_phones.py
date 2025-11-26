from odoo import models, fields

class KojtoBasePhones(models.Model):
    _name = "kojto.base.phones"
    _description = "Kojto Phones"
    _rec_name = "name"
    _order = "name desc"

    active = fields.Boolean(string="Is Active", default=True)
    name = fields.Char(string="Phone")
