from odoo import api, fields, models, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from io import BytesIO
from PIL import Image
import pytz
import base64
import numpy as np
import logging

_logger = logging.getLogger(__name__)


class KojtoHrTimeTracking(models.Model):
    _name = "kojto.hr.time.tracking"
    _description = "Kojto Hr Time Tracking"
    _order = "datetime_start desc"
    _rec_name = "subcode_id"

    employee_id = fields.Many2one("kojto.hr.employees", default=lambda self: self.get_current_employee(), string="Employee", required=True, index=True)
    employee_name_2 = fields.Char(related="employee_id.name_2", string="Employee Name 2")
    user_id = fields.Many2one(related="employee_id.user_id", string="Associated User")

    datetime_start = fields.Datetime(string="From", default=lambda self: self.get_utc_from_local(8), required=True, index=True)
    datetime_end = fields.Datetime(string="To")
    total_hours = fields.Float(string="hrs", compute="compute_total_hours", store=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    subcode_description = fields.Char(related="subcode_id.description")
    code_id = fields.Many2one(related="subcode_id.code_id", string="Code")
    comment = fields.Char(string="Comment")

    credited_subcode_id = fields.Many2one("kojto.commission.subcodes", string="Credited Subcode", compute="_compute_credited_subcode_id", store=True)
    value_in_BGN = fields.Float(string="Value in BGN", digits=(12, 2), compute="_compute_value_in_BGN", store=True)
    value_in_EUR = fields.Float(string="Value in EUR", digits=(12, 2), compute="_compute_value_in_EUR", store=True)

    @api.depends("total_hours", "subcode_id", "employee_id", "datetime_start")
    def _compute_credited_subcode_id(self):
        for record in self:
            if not record.total_hours or not record.subcode_id or not record.employee_id:
                record.credited_subcode_id = False
                continue

            # Get the employee's subcode rate for this employee and date (ignore subcode_id filter)
            # Convert datetime_start to date for comparison with date_start field
            record_date = record.datetime_start.date() if record.datetime_start else None
            subcode_rate = self.env['kojto.hr.employee.subcode.rates'].search([
                ('employee_id', '=', record.employee_id.id),
                ('date_start', '<=', record_date),
            ], order='date_start desc', limit=1) if record_date else None

            if subcode_rate:
                record.credited_subcode_id = subcode_rate.subcode_id
            else:
                record.credited_subcode_id = False

    @api.depends("total_hours", "subcode_id", "employee_id", "datetime_start")
    def _compute_value_in_BGN(self):
        for record in self:
            if not record.total_hours or not record.subcode_id or not record.employee_id:
                record.value_in_BGN = 0.0
                continue

            # Get the employee's subcode rate for this employee and date (ignore subcode_id filter)
            # Convert datetime_start to date for comparison with date_start field
            record_date = record.datetime_start.date() if record.datetime_start else None
            subcode_rate = self.env['kojto.hr.employee.subcode.rates'].search([
                ('employee_id', '=', record.employee_id.id),
                ('date_start', '<=', record_date),
            ], order='date_start desc', limit=1) if record_date else None

            if subcode_rate:
                record.value_in_BGN = record.total_hours * subcode_rate.hour_rate_in_BGN
            else:
                record.value_in_BGN = 0.0

    @api.depends("total_hours", "subcode_id", "employee_id", "datetime_start")
    def _compute_value_in_EUR(self):
        for record in self:
            if not record.total_hours or not record.subcode_id or not record.employee_id:
                record.value_in_EUR = 0.0
                continue

            # Get the employee's subcode rate for this employee and date (ignore subcode_id filter)
            # Convert datetime_start to date for comparison with date_start field
            record_date = record.datetime_start.date() if record.datetime_start else None
            subcode_rate = self.env['kojto.hr.employee.subcode.rates'].search([
                ('employee_id', '=', record.employee_id.id),
                ('date_start', '<=', record_date),
            ], order='date_start desc', limit=1) if record_date else None

            if subcode_rate:
                record.value_in_EUR = record.total_hours * subcode_rate.hour_rate_in_EUR
            else:
                record.value_in_EUR = 0.0

    def get_utc_from_local(self, hour):
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)
        local_time = utc_now.astimezone(user_timezone).replace(hour=hour, minute=0, second=0, microsecond=0)
        return local_time.astimezone(pytz.utc).replace(tzinfo=None)

    def is_working_day(self, date):
        """Check if a given date is a working day based on KojtoHrWorkingDays model"""
        working_day = self.env['kojto.hr.working.days'].search([('date', '=', date)], limit=1)
        if working_day:
            return working_day.is_working_day
        else:
            # If no record exists, assume it's a working day (except weekends)
            weekday = date.weekday()
            return weekday < 5  # Monday=0, Sunday=6, so weekdays 0-4 are working days

    def get_first_working_day_of_month(self, year, month):
        """Get the first working day of a given month"""
        first_day = datetime(year, month, 1).date()
        # Search for the first working day in the month
        working_day = self.env['kojto.hr.working.days'].search([
            ('date', '>=', first_day),
            ('date', '<', (first_day + relativedelta(months=1))),
            ('is_working_day', '=', True),
        ], order='date asc', limit=1)

        if working_day:
            return working_day.date
        else:
            # Fallback: find first weekday if no working days are defined
            current_date = first_day
            while current_date.month == month:
                if current_date.weekday() < 5:  # Monday=0, Sunday=6
                    return current_date
                current_date += timedelta(days=1)
            return first_day  # Fallback to first day if no weekday found

    def create_period_records(self, vals):
        """Create separate records for each working day in the period"""
        datetime_start = vals.get("datetime_start")
        datetime_end = vals.get("datetime_end")

        if not datetime_start or not datetime_end:
            return [vals]

        # Parse datetime strings - they come as naive UTC datetimes from Odoo
        start_dt = fields.Datetime.from_string(datetime_start)
        end_dt = fields.Datetime.from_string(datetime_end)
        # Reverse if start is after end
        if start_dt > end_dt:
            datetime_start, datetime_end = datetime_end, datetime_start
            start_dt, end_dt = end_dt, start_dt
            vals["datetime_start"] = datetime_start
            vals["datetime_end"] = datetime_end

        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)

        # Convert UTC datetimes to user timezone
        start_utc = pytz.utc.localize(start_dt)
        end_utc = pytz.utc.localize(end_dt)
        start_local = start_utc.astimezone(user_timezone)
        end_local = end_utc.astimezone(user_timezone)

        start_date = start_local.date()
        end_date = end_local.date()

        # Extract start and end times
        start_time = start_local.time()
        end_time = end_local.time()

        records = []
        current_date = start_date

        while current_date <= end_date:
            # Check if current date is a working day
            if self.is_working_day(current_date):
                # Create datetime objects for the current day in local timezone
                day_start_local = user_timezone.localize(
                    datetime.combine(current_date, start_time)
                )
                day_end_local = user_timezone.localize(
                    datetime.combine(current_date, end_time)
                )

                # Convert to UTC for storage (Odoo expects naive UTC datetimes)
                day_start_utc = day_start_local.astimezone(pytz.utc).replace(tzinfo=None)
                day_end_utc = day_end_local.astimezone(pytz.utc).replace(tzinfo=None)

                # Create record for this working day
                day_vals = vals.copy()
                day_vals.update({
                    "datetime_start": fields.Datetime.to_string(day_start_utc),
                    "datetime_end": fields.Datetime.to_string(day_end_utc),
                })
                records.append(day_vals)

            current_date += timedelta(days=1)

        return records

    def _ensure_contract_and_rate(self, employee_id, datetime_start):
        """Raise UserError if employee lacks valid contract or subcode rate for datetime_start."""
        if not employee_id or not datetime_start:
            return

        dt_start = fields.Datetime.from_string(datetime_start) if isinstance(datetime_start, str) else datetime_start
        # Convert datetime to date for comparison with date_start fields
        date_start = dt_start.date() if dt_start else None

        if not date_start:
            return

        contract_domain = [
            ('employee_id', '=', employee_id),
            ('date_start', '<=', date_start),
            '|',
            ('date_end', '>=', date_start),
            ('date_end', '=', False),
        ]
        has_contract = bool(self.env['kojto.hr.employees.contracts'].search(contract_domain, limit=1))

        subcode_rate_domain = [
            ('employee_id', '=', employee_id),
            ('date_start', '<=', date_start),
        ]
        has_subcode_rate = bool(self.env['kojto.hr.employee.subcode.rates'].search(subcode_rate_domain, limit=1))

        missing_elements = []
        if not has_contract:
            missing_elements.append(_("a valid contract"))
        if not has_subcode_rate:
            missing_elements.append(_("a subcode rate"))

        if missing_elements:
            employee_name = self.env['kojto.hr.employees'].browse(employee_id).name or employee_id
            missing_text = _(" and ").join(missing_elements)
            raise UserError(_("Cannot create time tracking for %(employee)s on %(date)s because %(missing)s is missing.") % {
                'employee': employee_name,
                'date': dt_start.strftime("%Y-%m-%d"),
                'missing': missing_text,
            })

    @api.model
    def create(self, vals_list):
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        all_new_vals = []
        for vals in vals_list:
            datetime_start, datetime_end = vals.get("datetime_start"), vals.get("datetime_end")
            if datetime_start and datetime_end:
               # Reverse if start is after end
                start_dt_raw = fields.Datetime.from_string(datetime_start)
                end_dt_raw = fields.Datetime.from_string(datetime_end)
                if start_dt_raw > end_dt_raw:
                    datetime_start, datetime_end = datetime_end, datetime_start
                    vals["datetime_start"] = datetime_start
                    vals["datetime_end"] = datetime_end
                start_dt = start_dt_raw.astimezone(pytz.utc)
                end_dt = end_dt_raw.astimezone(pytz.utc)
                user_tz = self.env.user.tz or "UTC"
                user_timezone = pytz.timezone(user_tz)
                start_local = start_dt.astimezone(user_timezone)
                end_local = end_dt.astimezone(user_timezone)

                # Calculate total hours
                total_hours = (end_local - start_local).total_seconds() / 3600.0

                # Check if this is a single-day record with more than 24 hours
                if start_local.date() == end_local.date() and total_hours > 24:
                    raise UserError("A single day cannot have more than 24 hours of work. Please split your time tracking into multiple days.")

                # Split if needed - always create separate records for each day when spanning multiple days
                if start_local.date() != end_local.date():
                    period_records = self.create_period_records(vals)
                    all_new_vals.extend(period_records)
                else:
                    # Single day record - validate it doesn't exceed 24 hours
                    total_hours = (end_local - start_local).total_seconds() / 3600.0
                    if total_hours > 24:
                        raise UserError("A single day cannot have more than 24 hours of work. Please split your time tracking into multiple days.")
                    all_new_vals.append(vals)
            else:
                all_new_vals.append(vals)

        # Ensure employee has valid contract and subcode rate
        for vals in all_new_vals:
            employee_id = vals.get("employee_id")
            datetime_start = vals.get("datetime_start")
            if employee_id and datetime_start:
                self._ensure_contract_and_rate(employee_id, datetime_start)

        # Check for overlaps for all new records before creating any
        for vals in all_new_vals:
            employee_id = vals.get("employee_id")
            datetime_start = vals.get("datetime_start")
            datetime_end = vals.get("datetime_end")
            if not (employee_id and datetime_start and datetime_end):
                continue
            # Check overlap with time tracking
            domain = [
                ("employee_id", "=", employee_id),
                ("datetime_start", "<", datetime_end),
                ("datetime_end", ">", datetime_start),
            ]
            overlapping = self.env["kojto.hr.time.tracking"].search(domain)
            if overlapping:
                raise UserError("The time span overlaps with another record for the same employee.")
            # Check overlap with leave
            # Convert datetime to date for comparison with leave date fields
            start_dt = fields.Datetime.from_string(datetime_start) if isinstance(datetime_start, str) else datetime_start
            end_dt = fields.Datetime.from_string(datetime_end) if isinstance(datetime_end, str) else datetime_end
            start_date = start_dt.date() if start_dt else None
            end_date = end_dt.date() if end_dt else None

            if start_date and end_date:
                leave_domain = [
                    ("employee_id", "=", employee_id),
                    ("date_start", "<=", end_date),
                    ("date_end", ">=", start_date),
                    ("leave_status", "!=", "denied"),
                ]
                if self.env["kojto.hr.leave.management"].search(leave_domain):
                    raise UserError("This time tracking record overlaps with a leave period for this employee.")

        # If all checks pass, create all at once
        created_records = super(KojtoHrTimeTracking, self).create(all_new_vals)
        created_records.sudo()._notify_users_about_past_events("created")

        return created_records

    def write(self, vals):
        # Reverse datetime_start and datetime_end if both provided and start is after end
        datetime_start = vals.get("datetime_start")
        datetime_end = vals.get("datetime_end")
        if datetime_start and datetime_end:
            start_dt = fields.Datetime.from_string(datetime_start) if isinstance(datetime_start, str) else datetime_start
            end_dt = fields.Datetime.from_string(datetime_end) if isinstance(datetime_end, str) else datetime_end
            if start_dt > end_dt:
                vals["datetime_start"], vals["datetime_end"] = vals["datetime_end"], vals["datetime_start"]

        # Validate contract and subcode rate before applying changes
        if any(field in vals for field in ("employee_id", "datetime_start")):
            for record in self:
                employee_id = vals.get("employee_id", record.employee_id.id)
                record_datetime_start = vals.get("datetime_start", record.datetime_start)
                if employee_id and record_datetime_start:
                    self._ensure_contract_and_rate(employee_id, record_datetime_start)

        result = super(KojtoHrTimeTracking, self).write(vals)

        # Notify users about past month events
        if 'datetime_start' in vals or 'datetime_end' in vals or "subcode_id" in vals:
            self.sudo()._notify_users_about_past_events("modified")

        return result

    @api.model
    def get_current_employee(self):
        user_id = self.env.user.id
        employee = self.env["kojto.hr.employees"].search([("user_id", "=", user_id)], limit=1)
        return employee.id if employee else False

    @api.depends("datetime_start", "datetime_end")
    def compute_total_hours(self):
        for record in self:
            if record.datetime_start and record.datetime_end:
                record.total_hours = (record.datetime_end - record.datetime_start).total_seconds() / 3600.0
            else:
                record.total_hours = 0.0

    def open_time_tracking_list_view(self):
        action_id = self.env.ref("kojto_hr.action_kojto_hr_time_tracking").id
        url = f"/web#action={action_id}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    @api.constrains("employee_id", "datetime_start", "datetime_end")
    def check_time_overlap(self):
        for record in self:
            # Check overlap with other time tracking records
            domain = [
                ("employee_id", "=", record.employee_id.id),
                ("datetime_start", "<", record.datetime_end),
                ("datetime_end", ">", record.datetime_start),
                ("id", "!=", record.id)
            ]
            overlapping_records = self.search(domain)
            if overlapping_records:
                raise UserError("The time span overlaps with another record for the same employee.")

            # Check overlap with leave records
            # Convert datetime to date for comparison with leave date fields
            if record.datetime_start and record.datetime_end:
                start_date = record.datetime_start.date()
                end_date = record.datetime_end.date()
                overlapping_leaves = self.env["kojto.hr.leave.management"].search([
                    ("employee_id", "=", record.employee_id.id),
                    ("date_start", "<=", end_date),
                    ("date_end", ">=", start_date),
                    ("leave_status", "!=", "denied"),
                ])
                if overlapping_leaves:
                    raise UserError("This time tracking record overlaps with a leave period for this employee.")

    @api.constrains("datetime_start", "datetime_end")
    def check_max_hours_per_day(self):
        for record in self:
            if record.datetime_start and record.datetime_end:
                # Convert to user timezone for accurate day calculation
                user_tz = self.env.user.tz or "UTC"
                user_timezone = pytz.timezone(user_tz)
                start_local = record.datetime_start.astimezone(pytz.utc).astimezone(user_timezone)
                end_local = record.datetime_end.astimezone(pytz.utc).astimezone(user_timezone)

                # Check if this is a single-day record
                if start_local.date() == end_local.date():
                    total_hours = (end_local - start_local).total_seconds() / 3600.0
                    if total_hours > 24:
                        raise UserError("A single day cannot have more than 24 hours of work. Please split your time tracking into multiple days.")

    def unlink(self):
        return super(KojtoHrTimeTracking, self).unlink()

    def compute_value_in_BGN_and_EUR_batch(self):
        """
        Compute value_in_BGN, value_in_EUR, and credited_subcode_id for the current time tracking records.
        This method bypasses the write validation for previous months.
        """
        for record in self:
            if not record.total_hours or not record.subcode_id or not record.employee_id:
                value_in_BGN = 0.0
                value_in_EUR = 0.0
                credited_subcode_id = None
            else:
                # Get the employee's subcode rate for this employee and date (ignore subcode_id filter)
                # Convert datetime_start to date for comparison with date_start field
                record_date = record.datetime_start.date() if record.datetime_start else None
                subcode_rate = self.env['kojto.hr.employee.subcode.rates'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_start', '<=', record_date),
                ], order='date_start desc', limit=1) if record_date else None

                if subcode_rate:
                    value_in_BGN = record.total_hours * subcode_rate.hour_rate_in_BGN
                    value_in_EUR = record.total_hours * subcode_rate.hour_rate_in_EUR
                    credited_subcode_id = subcode_rate.subcode_id.id
                else:
                    value_in_BGN = 0.0
                    value_in_EUR = 0.0
                    credited_subcode_id = None

            # Update value_in_BGN, value_in_EUR, and credited_subcode_id fields directly in the database to bypass validation
            if credited_subcode_id is not None:
                self.env.cr.execute(
                    'UPDATE kojto_hr_time_tracking SET "value_in_BGN" = %s, "value_in_EUR" = %s, credited_subcode_id = %s WHERE id = %s',
                    (value_in_BGN, value_in_EUR, credited_subcode_id, record.id)
                )
            else:
                self.env.cr.execute(
                    'UPDATE kojto_hr_time_tracking SET "value_in_BGN" = %s, "value_in_EUR" = %s, credited_subcode_id = NULL WHERE id = %s',
                    (value_in_BGN, value_in_EUR, record.id)
                )

        return {
            'message': f'Successfully computed value_in_BGN, value_in_EUR, and credited_subcode_id for {len(self)} records'
        }


    def action_export_grouped_csv_action(self):
        """Entry point from Actions menu: redirects to a URL that streams the CSV.
        We pack current domain and group_by from context into the URL payload.
        """
        ctx = dict(self.env.context or {})
        # Get domain: prefer active_domain if present, else fall back to selected ids
        domain = ctx.get('active_domain') or []
        if not domain and self:
            domain = [('id', 'in', self.ids)]

        # Resolve group_by from context (support multiple common keys)
        group_by_ctx = ctx.get('group_by') or ctx.get('groupby') or ctx.get('ordered_groupby')
        group_by = []
        if isinstance(group_by_ctx, (list, tuple)):
            group_by = [g for g in group_by_ctx if g]
        elif isinstance(group_by_ctx, str):
            # Accept comma-separated values and trim
            group_by = [g.strip() for g in group_by_ctx.split(',') if g.strip()]

        # Default group_by if not provided from context
        if not group_by:
            group_by = ['employee_id', 'code_id']

        payload = {
            'model': self._name,
            'domain': domain,
            'group_by': group_by,
            # Narrow context to avoid very large query-string
            'company_id': self.env.company.id,
            'lang': ctx.get('lang'),
            'tz': ctx.get('tz') or self.env.user.tz,
        }

        # Encode payload compactly
        import json
        params_b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')

        return {
            'type': 'ir.actions.act_url',
            'url': f"/kojto_hr/time_tracking/export_csv?payload={params_b64}",
            'target': 'self',
        }

    @api.constrains('datetime_start')
    def _check_datetime_start_by_user_group(self):
        for record in self:
            if not record.datetime_start:
                continue

            current_user = self.env.user
            record_date = record.datetime_start.date()
            today = datetime.now().date()
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
            previous_month_start = (datetime.now().replace(day=1) - relativedelta(months=1)).date()

            # Kojto Administrator - no restrictions
            if current_user.has_group('kojto_base.kojto_administrator'):
                continue

            # Kojto Human Resources - no restrictions
            elif current_user.has_group('kojto_base.kojto_hr'):
                continue

            # Kojto Assistant - can the current and previous month
            elif current_user.has_group('kojto_base.kojto_assistant'):
                if record_date < previous_month_start:
                    raise ValidationError(
                        f"You can only enter hours for the current and previous month!!\n"
                        f"The earliest date allowed is: {previous_month_start.strftime('%d.%m.%Y')}"
                    )

            # All other groups - current month + previous month until first working day
            # Automatically applied to any user who is NOT an Administrator, HR or Assistant
            else:
                # Get the first working day of the current month
                first_working_day = record.get_first_working_day_of_month(today.year, today.month)

                # If today is on or before the first working day, allow previous month records
                if today <= first_working_day:
                    # Allow previous month and current month
                    if record_date < previous_month_start:
                        raise ValidationError(
                            f"You can only enter hours for the current and previous month!\n"
                            f"The earliest date allowed is: {previous_month_start.strftime('%d.%m.%Y')}"
                        )
                else:
                    # After first working day - only allow current month
                    if record_date < current_month_start:
                        raise ValidationError(
                            f"You can only enter hours for the current month!\n"
                            f"The earliest date allowed is: {current_month_start.strftime('%d.%m.%Y')}"
                        )


    def _notify_users_about_past_events(self, action):
            """Notify HR users about past events"""
            try:
                current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                past_events = self.filtered(lambda e: e.datetime_start and e.datetime_start < current_month_start)

                if not past_events:
                    return

                notification_group = self.env.ref('kojto_base.kojto_hr', raise_if_not_found=False)

                if not notification_group:
                    _logger.warning("HR group 'kojto_base.kojto_hr' not found")
                    return

                _logger.info(f"Notification group: {notification_group}")

                hr_users = self.env['res.users'].search([
                    ('group_ids', 'in', [notification_group.id]),
                    ('active', '=', True),
                    ('email', '!=', False)
                ])
                _logger.info(f"HR users: {hr_users}")

                if not hr_users:
                    _logger.warning("No active HR users with email found")
                    return

                _logger.info(f"Found {len(hr_users)} HR users to notify: {', '.join(hr_users.mapped('name'))}")

                for event in past_events:
                    self._send_past_event_notification_email(event, hr_users, action)

            except Exception as e:
                _logger.error(f"Error in _notify_users_about_past_events: {e}")


    def _send_past_event_notification_email(self, event, users_to_notify, action):
        """Send email notification about past event to users"""
        try:
            subject = f"HR Notification: {action.title()} Time Tracking Event"

            body = f"""
            <p>A time tracking event has been {action} in the past month:</p>
            <ul>
                <li><strong>Employee:</strong> {event.employee_id.name if event.employee_id else 'N/A'}</li>
                <li><strong>Start:</strong> {event.datetime_start.strftime('%Y-%m-%d %H:%M') if event.datetime_start else 'N/A'}</li>
                <li><strong>End:</strong> {event.datetime_end.strftime('%Y-%m-%d %H:%M') if event.datetime_end else 'N/A'}</li>
                <li><strong>Total Hours:</strong> {event.total_hours}</li>
                <li><strong>Comment:</strong> {event.comment or 'N/A'}</li>
            </ul>
            <p>This event occurred in a past month and may require attention.</p>
            """

            # Send email to each user
            for user in users_to_notify:
                if user.email:
                    mail_values = {
                        'subject': subject,
                        'body_html': body,
                        'email_from': self.env.company.email or self.env.user.email,
                        'email_to': user.email,
                        'auto_delete': True,
                    }

                    try:
                        mail = self.env['mail.mail'].create(mail_values)
                        mail.send()
                    except Exception as e:
                        _logger.error(f"Failed to send email to {user.name} ({user.email}): {e}")

        except Exception as e:
            _logger.error(f"Error sending notification email: {e}")
            import traceback
            _logger.error(f"Full traceback: {traceback.format_exc()}")


