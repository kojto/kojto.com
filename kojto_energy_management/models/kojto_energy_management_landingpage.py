# -*- coding: utf-8 -*-

from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_kojto_energy_management_list_view(self):
        action_id = self.env.ref("kojto_energy_management.action_kojto_energy_management_devices").id
        url = f"/web#action={action_id}&search_default_filter_active=1"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

