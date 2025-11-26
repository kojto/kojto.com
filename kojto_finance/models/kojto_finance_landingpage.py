# kojto_finance/models/kojto_finance_landingpage.py
from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_invoices_list_view(self):
        action_id = self.env.ref("kojto_finance.action_kojto_finance_invoices").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
