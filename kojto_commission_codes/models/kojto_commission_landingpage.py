from odoo import models

class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_comission_codes_list_view(self):
        action_id = self.env.ref("kojto_commission_codes.action_kojto_commission_codes").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
