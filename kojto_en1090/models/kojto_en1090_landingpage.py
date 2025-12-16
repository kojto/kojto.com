from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = 'kojto.landingpage'

    def open_en1090_document_bundles_list_view(self):
        action_id = self.env.ref('kojto_en1090.action_kojto_en1090_document_bundles').id
        url = f"/web#action={action_id}"

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }
