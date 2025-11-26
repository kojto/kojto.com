from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    # ... existing code for KojtoLandingpages class ...

    def open_offers_list_view(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offers",
            "view_mode": "list,form",
            "target": "current",
        }
