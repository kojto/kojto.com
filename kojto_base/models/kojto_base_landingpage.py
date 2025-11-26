from odoo import models

class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_base_list_view(self):
        action_id = self.env.ref("kojto_base.action_kojto_base_banks").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
