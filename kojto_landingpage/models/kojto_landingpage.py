from odoo import fields, models


class KojtoLandingpage(models.Model):
    _name = "kojto.landingpage"
    _description = "Kojto Landing Page"
    _rec_name = "name"

    name = fields.Char(default="Home")

    def open_landingpage(self):
        first_record = self.search([], limit=1, order="id")
        action_id = self.env.ref("kojto_landingpage.action_kojto_landingpage").id

        if not first_record:
            first_record = self.create({})

        url = f"/web#id={first_record.id}&view_type=form&model={self._name}&action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_apps_list_view(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/odoo/apps",
            "target": "self",
        }

    def open_settings_list_view(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/odoo/settings",
            "target": "self",
        }
