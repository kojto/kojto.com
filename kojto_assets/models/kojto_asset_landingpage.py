# -*- coding: utf-8 -*-
from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_assets_list_view(self):
        action_id = self.env.ref("kojto_assets.action_kojto_assets").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
