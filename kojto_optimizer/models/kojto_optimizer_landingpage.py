#$ kojto_optimizer/models/kojto_optimizer_landingpage.py

from odoo import models

class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_optimizer_1D_packages_list_view(self):
        action_id = self.env.ref("kojto_optimizer.action_kojto_optimizer_1d").id
        url = f"/web#action={action_id}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}
