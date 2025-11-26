from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_deliveries_list_view(self):
        action_id = self.env.ref("kojto_deliveries.action_kojto_deliveries").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
