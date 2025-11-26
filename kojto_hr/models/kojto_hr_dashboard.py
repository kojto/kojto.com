"""
Kojto HR Dashboard Model

Purpose:
--------
Core dashboard management model that handles dashboard creation,
date range management, and employee content generation.
"""

from odoo import models, fields, api
from datetime import timedelta, datetime, date, time
from dateutil.relativedelta import relativedelta
import pytz


class KojtoHrDashboard(models.Model):
    _name = "kojto.hr.dashboard"
    _description = "Kojto HR Dashboard"

    name = fields.Char(string="Name", store=True, default=lambda self: f"{self.env.user.name}'s HR Dashboard")
    employee_ids = fields.Many2many("kojto.hr.employees", string="Employees")
    datetime_start = fields.Datetime(string="From date:", required=True, store=True, default=lambda self: self.get_utc_from_local(8))
    datetime_end = fields.Datetime(string="To date:", required=True, store=True, default=lambda self: self.get_utc_from_local(17))

    content = fields.One2many("kojto.hr.dashboard.contents", "dashboard_id", string="Contents")

    def create_dashboard_content(self):
        self.content.unlink()
        employee_model = self.env["kojto.hr.employees"]
        employees = self.employee_ids or employee_model.search([])

        content_model = self.env["kojto.hr.dashboard.contents"]

        for employee in employees:
            content_model.create(
                {
                    "dashboard_id": self.id,
                    "employee_id": employee.id,
                }
            )

    def get_utc_from_local(self, hour):
        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        now_local = datetime.now(user_tz).replace(hour=hour, minute=0, second=0, microsecond=0)
        return now_local.astimezone(pytz.utc).replace(tzinfo=None)

    def _convert_to_utc(self, local_date, time_point):
        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        local_dt = user_tz.localize(datetime.combine(local_date, time_point))
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def set_dates_to_current_week(self):
        today = datetime.now().date()
        self.datetime_start = self._convert_to_utc(today - timedelta(days=today.weekday()), datetime.min.time())
        self.datetime_end = self._convert_to_utc(self.datetime_start.date() + timedelta(days=6), datetime.max.time())

    def set_dates_to_today(self):
        today = datetime.now().date()
        self.datetime_start = self._convert_to_utc(today, datetime.min.time())
        self.datetime_end = self._convert_to_utc(today, datetime.max.time())

    def set_dates_to_current_month(self):
        today = datetime.now().date()
        first_day = today.replace(day=1)
        last_day = (first_day + relativedelta(months=1)) - timedelta(days=1)
        self.datetime_start = self._convert_to_utc(first_day, datetime.min.time())
        self.datetime_end = self._convert_to_utc(last_day, datetime.max.time())

    def forward_one_month(self):
        self.ensure_one()
        self.datetime_start += relativedelta(months=1)
        self.datetime_end += relativedelta(months=1)

    def backward_one_month(self):
        self.ensure_one()
        self.datetime_start -= relativedelta(months=1)
        self.datetime_end -= relativedelta(months=1)

    def forward_one_year(self):
        self.ensure_one()
        self.datetime_start += relativedelta(years=1)
        self.datetime_end += relativedelta(years=1)

    def backward_one_year(self):
        self.ensure_one()
        self.datetime_start -= relativedelta(years=1)
        self.datetime_end -= relativedelta(years=1)
