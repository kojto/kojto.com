from odoo import models


class KojtoLandingPage(models.Model):
    _inherit = "kojto.landingpage"

    def open_sales_list_view(self):
        action_id = self.env.ref("kojto_sales.action_kojto_sale_leads").id  # Updated action name
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
