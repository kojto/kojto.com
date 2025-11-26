from odoo import models

class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_kojto_warehouses_list_view(self):
        action_id = self.env.ref("kojto_warehouses.action_kojto_warehouses_batches").id
        url = f"/web#action={action_id}&search_default_active=1"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
