# kojto_products/models/kojto_product_landingpage.py
from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_component_list_view(self):
        action_id = self.env.ref("kojto_products.action_kojto_product_component").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
