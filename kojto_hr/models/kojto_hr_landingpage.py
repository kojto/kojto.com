"""
Kojto HR Landing Page Model

Purpose:
--------
Extends the landing page model to provide quick access to HR-related
views and functionality through the landing page interface.
"""

from odoo import models


class KojtoLandingpage(models.Model):
    _inherit = "kojto.landingpage"

    def open_employees_list_view(self):
        """Open the employees list view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_employees").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_time_tracking_list_view(self):
        """Open the time tracking list view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_time_tracking").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_time_tracking_image_calendar_view(self):
        """Open the time tracking calendar view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_calendar_event_calendar").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_business_trips_list_view(self):
        """Open the business trips list view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_business_trips").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_leave_management_list_view(self):
        """Open the leave management list view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_leave_management").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_mycalendar_list_view(self):
        """Open the employee calendar list view from the landing page."""
        action_id = self.env.ref("kojto_hr.action_kojto_hr_employees").id
        url = f"/web#action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def open_hr_dashboard(self):
        """Open or create the HR dashboard for the current user."""
        dashboard_record = self.env["kojto.hr.dashboard"].search(
            [("create_uid", "=", self.env.user.id)],
            limit=1,
            order="id"
        )
        action_id = self.env.ref("kojto_hr.action_kojto_hr_dashboard").id

        if not dashboard_record:
            dashboard_record = self.env["kojto.hr.dashboard"].create({
                "create_uid": self.env.user.id,
                "name": f"{self.env.user.name}'s HR Dashboard",
            })

        url = f"/web#id={dashboard_record.id}&view_type=form&model=kojto.hr.dashboard&action={action_id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }
