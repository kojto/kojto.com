from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_face_recognition_form_view(self):
        action_id = self.env.ref("kojto_hr_face_recognition.action_kojto_hr_face_recognition").id
        url = f"/web#action={action_id}&view_type=form&mode=edit&id="

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
