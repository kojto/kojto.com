from odoo import models, fields, api, _

class KojtoOfferSurcharges(models.Model):
    _name = "kojto.offer.surcharges"
    _description = "Kojto Surcharges"
    _rec_name = "name"
    _order = "name desc"

    name = fields.Char(string="Name")
    surcharge = fields.Float(string="Fee in %", digits=(16, 2), default=16.0)

    def open_o2m_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.surcharges",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }
