from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_inquiries_list_view(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.inquiries",
            "view_mode": "list,form",
            "target": "current",
        }
