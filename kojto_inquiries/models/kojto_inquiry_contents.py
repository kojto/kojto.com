from odoo import models, fields, api, _

class KojtoInquiryContents(models.Model):
    _name = "kojto.inquiry.contents"
    _description = "Kojto Inquiry Contents"
    _rec_name = "name"
    _order = "position asc, id asc"

    name = fields.Char(string="Description", size=200)
    position = fields.Char(string="№", size=5)

    inquiry_id = fields.Many2one("kojto.inquiries", string="Inquiry", ondelete="set null")
    currency_id = fields.Many2one("res.currency", string="", related="inquiry_id.currency_id", readonly=True)
    quantity = fields.Float(string="Quantity", digits=(16, 2))
    unit_id = fields.Many2one("kojto.base.units", string="Unit")

    def open_o2m_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.inquiry.contents",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
