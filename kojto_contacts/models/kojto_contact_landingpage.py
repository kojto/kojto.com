# -*- coding: utf-8 -*-
from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_contacts_list_view(self):
        action_id = self.env.ref("kojto_contacts.action_kojto_contacts").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
