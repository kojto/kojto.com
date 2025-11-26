from odoo import models, fields

class KojtoBaseInsurances(models.Model):
    _name = "kojto.base.insurances"
    _description = "Kojto Docs Insurance"
    _rec_name = "name"
    _order = "name desc"

    description = fields.Text("Description")
    active = fields.Boolean("Is Active", default=True)
    language_id = fields.Many2one("res.lang", string="Language")
    name = fields.Char("Name")
    date_start = fields.Date("Valid From", default=fields.Date.today, required=True)
    date_end = fields.Date("Valid To")
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.base.insurances'), ('res_id', '=', id)]")
