"""
Kojto Technical Document Landing Page Model

Purpose:
--------
Extends the landing page model to provide quick access to technical
documentation through the landing page interface.
"""

from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = 'kojto.landingpage'

    def open_technical_docs_list_view(self):
        """Open the technical documents list view from the landing page."""
        action_id = self.env.ref('kojto_technical_docs.action_kojto_technical_docs').id
        url = f"/web#action={action_id}"

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }
