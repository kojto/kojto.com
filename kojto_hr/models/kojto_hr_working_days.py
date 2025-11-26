from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta
import calendar

class KojtoHrWorkingDays(models.Model):
    _name = "kojto.hr.working.days"
    _description = "Kojto Working Days"
    _rec_name = "display_name"

    date = fields.Date(string="Date", required=True, index=True)
    is_working_day = fields.Boolean(string="Is Working Day", default=True)
    day_type = fields.Selection([
        ('regular', 'Regular Working Day'),
        ('weekend', 'Weekend'),
        ('public_holiday', 'Public Holiday')
    ], string="Day Type", required=True, default='regular')
    description = fields.Char(string="Description")
    display_name = fields.Char(string="Display Name", compute="compute_display_name", store=False)

    @api.model
    def generate_calendar(self):
        current_year = date.today().year
        start_year = current_year - 20
        end_year = current_year + 1

        holidays = [(1, 1), (3, 3), (5, 1), (5, 6), (5, 24), (9, 6), (9, 22), (12, 24), (12, 25), (12, 26)]

        existing_dates = self.search([]).mapped('date')
        records_to_create = []

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                for day in range(1, calendar.monthrange(year, month)[1] + 1):
                    dt = date(year, month, day)
                    if dt not in existing_dates:
                        if dt.weekday() in (5, 6):
                            day_type = 'weekend'
                            is_working = False
                            desc = "Weekend"
                        elif (dt.month, dt.day) in holidays:
                            day_type = 'public_holiday'
                            is_working = False
                            desc = "Public Holiday"
                        else:
                            day_type = 'regular'
                            is_working = True
                            desc = "Regular Working Day"

                        records_to_create.append({
                            'date': dt,
                            'is_working_day': is_working,
                            'day_type': day_type,
                            'description': desc
                        })

        if records_to_create:
            self.create(records_to_create)

    #@api.model
    def add_one_year(self):
        latest_date = self.search([], order='date desc', limit=1).date

        if not latest_date:
            raise UserError("No existing records found to extend from.")

        start_date = latest_date + timedelta(days=1)
        end_date = date(start_date.year + 1, start_date.month, start_date.day) - timedelta(days=1)

        holidays = [(1, 1), (3, 3), (5, 1), (5, 6), (5, 24), (9, 6), (9, 22), (12, 24), (12, 25), (12, 26)]

        existing_dates = self.search([]).mapped('date')
        records_to_create = []

        current_date = start_date
        while current_date <= end_date:
            if current_date not in existing_dates:
                if current_date.weekday() in (5, 6):
                    day_type = 'weekend'
                    is_working = False
                    desc = "Weekend"
                elif (current_date.month, current_date.day) in holidays:
                    day_type = 'public_holiday'
                    is_working = False
                    desc = "Public Holiday"
                else:
                    day_type = 'regular'
                    is_working = True
                    desc = "Regular Working Day"

                records_to_create.append({
                    'date': current_date,
                    'is_working_day': is_working,
                    'day_type': day_type,
                    'description': desc
                })

            current_date += timedelta(days=1)

        if records_to_create:
            self.create(records_to_create)

    @api.depends("description")
    def compute_display_name(self):
        for record in self:
            record.display_name = f"{record.day_type}: {record.description}" if record.description else record.day_type
        return {}
