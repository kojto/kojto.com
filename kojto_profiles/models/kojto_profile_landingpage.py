#$ kojto_profiles/models/kojto_profile_landingpage.py

from odoo import models

class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_profile_batches_list_view(self):
        action_id = self.env.ref("kojto_profiles.action_kojto_profile_batches").id
        url = f"/web#action={action_id}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}
