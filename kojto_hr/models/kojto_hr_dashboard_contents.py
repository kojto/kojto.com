"""
Kojto HR Dashboard Contents Model

Purpose:
--------
Manages the content of HR dashboards, including employee work hours,
leave tracking, overtime calculations, and work hour balances.
"""

from odoo import models, fields, api
from datetime import datetime, timedelta, time
import pytz
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class KojtoHrDashboardContents(models.Model):
    _name = "kojto.hr.dashboard.contents"
    _description = "Kojto HR Dashboard Content"

    dashboard_id = fields.Many2one("kojto.hr.dashboard", string="Associated Dashboard", ondelete="cascade")
    employee_id = fields.Many2one("kojto.hr.employees", string="Employee")
    work_day_duration = fields.Float(string="Daily Work Hours", compute="compute_work_day_duration")

    paid_leave = fields.Float(string="Paid Leave Hours", compute="compute_hours_leave_paid")
    unpaid_leave = fields.Float(string="Unpaid Leave Hours", compute="compute_hours_leave_unpaid")
    sick_leave = fields.Float(string="Sick Leave Hours", compute="compute_hours_leave_sick")

    workhours = fields.Float(string="Actual Work Hours", compute="compute_workhours")
    norm = fields.Float(string="Expected Work Hours", compute="compute_norm")
    balance = fields.Float(string="Work Hours Balance", compute="compute_balance")
    total = fields.Float(string="Total Hours Accounted", compute="compute_total")
    overtime_working_day = fields.Float(string="Overtime +50%", compute="compute_overtime_working_day")
    overtime_weekend = fields.Float(string="Overtime +75%", compute="compute_overtime_weekend")
    overtime_public_holiday = fields.Float(string="Overtime +100%", compute="compute_overtime_public_holiday")
    no_record_days = fields.Integer(string="No record days", compute="compute_no_record_days")

    sum_overtime_working_day = fields.Float(string="Sum Overtime Working Day (Raw)", compute="compute_overtime_working_day")
    sum_overtime_weekend = fields.Float(string="Sum Overtime Weekend (Raw)", compute="compute_overtime_weekend")
    sum_overtime_holiday = fields.Float(string="Sum Overtime Holiday (Raw)", compute="compute_overtime_public_holiday")


    def convert_timezone_dashboard_dates(self):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        utc_tz = pytz.UTC
        # Convert start datetime from UTC to user timezone
        start_utc = self.dashboard_id.datetime_start.replace(tzinfo=utc_tz)
        start_local = start_utc.astimezone(user_tz)
        start_date = start_local.date()
        # Convert end datetime from UTC to user timezone
        end_utc = self.dashboard_id.datetime_end.replace(tzinfo=utc_tz)
        end_local = end_utc.astimezone(user_tz)
        end_date = end_local.date()

        return start_date, end_date

    def _get_contract_start_bounds(self):
        self.ensure_one()
        if not self.dashboard_id or not self.employee_id:
            return None, None

        dashboard_start_dt = self.dashboard_id.datetime_start
        dashboard_end_dt = self.dashboard_id.datetime_end
        if not dashboard_start_dt or not dashboard_end_dt:
            return None, None

        dashboard_start_date = dashboard_start_dt.date()
        dashboard_end_date = dashboard_end_dt.date()

        contract = self.env["kojto.hr.employees.contracts"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("date_start", "<=", dashboard_end_date),
                "|",
                ("date_end", ">=", dashboard_start_date),
                ("date_end", "=", False),
            ],
            order="date_start desc",
            limit=1,
        )

        if contract and contract.date_start:
            contract_start_date = contract.date_start
            contract_start_datetime = datetime.combine(contract_start_date, time.min)
            return contract_start_date, contract_start_datetime
        return None, None

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration")
    def compute_overtime_working_day(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                start_date, end_date = record.convert_timezone_dashboard_dates()
                contract_start_date, contract_start_datetime = record._get_contract_start_bounds()
                effective_start_date = contract_start_date if contract_start_date and contract_start_date > start_date else start_date
                dashboard_start_datetime = record.dashboard_id.datetime_start
                effective_start_datetime = (
                    contract_start_datetime
                    if contract_start_datetime and contract_start_datetime > dashboard_start_datetime
                    else dashboard_start_datetime
                )

                # Get working days in the period
                working_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", effective_start_date),
                            ("date", "<=", end_date),
                            ("is_working_day", "=", True),
                        ]
                    )
                    .mapped("date")
                )

                # Get work logs for employee in period
                work_logs = self.env["kojto.hr.time.tracking"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("datetime_start", ">=", effective_start_datetime),
                        ("datetime_end", "<=", end_date),
                    ]
                )

                _logger.info(f"work_logs: {work_logs}")

                _logger.info(f"work_logs: {work_logs}")

                # Build set of leave days
                leave_days = set()
                dashboard_end_date = record.dashboard_id.datetime_end.date() if record.dashboard_id.datetime_end else None
                dashboard_start_date = effective_start_date
                if dashboard_start_date and dashboard_end_date:
                    leave_records = self.env["kojto.hr.leave.management"].search([
                        ("employee_id", "=", record.employee_id.id),
                        ("leave_status", "!=", "denied"),
                        ("date_start", "<=", dashboard_end_date),
                        ("date_end", ">=", dashboard_start_date),
                    ])
                    for rec in leave_records:
                        if rec.date_start and rec.date_end:
                            current_date = rec.date_start
                            leave_end_date = rec.date_end
                            while current_date <= leave_end_date:
                                leave_days.add(current_date)
                                current_date += timedelta(days=1)
                _logger.info(f"leave_days: {leave_days}")

                # Remove leave days from working_days
                working_days_set = set(working_days)
                working_days_minus_leave = working_days_set - leave_days
                _logger.info(f"working_days_minus_leave: {working_days_minus_leave}")

                # Group logs by day
                logs_by_day = defaultdict(float)
                for log in work_logs:
                    log_date = log.datetime_start.date()
                    if log_date in working_days_minus_leave:
                        logs_by_day[log_date] += log.total_hours
                        _logger.info(f"log id: {log.id}, date: {log_date}, total_hours: {log.total_hours}")

                # For each working day (excluding leave), subtract work_day_duration once
                working_day_overtime = 0
                for day in working_days_minus_leave:
                    day_total = logs_by_day.get(day, 0.0)
                    overtime = day_total - record.work_day_duration
                    working_day_overtime += overtime
                    _logger.info(f"Day: {day}, total_hours: {day_total}, overtime: {overtime}")

                _logger.info(f"work_day_duration: {record.work_day_duration}")


                # Get paid leaves with 'извънредни' in the name
                dashboard_start_date = effective_start_date
                dashboard_end_date = record.dashboard_id.datetime_end.date() if record.dashboard_id.datetime_end else None
                if dashboard_start_date and dashboard_end_date:
                    extraordinary_leaves = self.env["kojto.hr.leave.management"].search([
                        ("employee_id", "=", record.employee_id.id),
                        ("leave_type_id.leave_group", "=", "paid"),
                        ("leave_status", "!=", "denied"),
                        ("date_start", "<=", dashboard_end_date),
                        ("date_end", ">=", dashboard_start_date),
                    ])
                    extraordinary_leaves = extraordinary_leaves.filtered(lambda l: "извънредни" in (l.leave_type_id.name or '').lower())

                    # Calculate total hours for these leaves (overlapping with the dashboard period)
                    extraordinary_leave_hours = 0
                    for leave in extraordinary_leaves:
                        from_date = max(dashboard_start_date, leave.date_start)
                        to_date = min(dashboard_end_date, leave.date_end)
                        # Only count days that are working days
                        days_total = sum(1 for dt in (from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)) if dt.weekday() not in (5, 6) and dt in working_days)
                        extraordinary_leave_hours += days_total * record.work_day_duration
                else:
                    extraordinary_leave_hours = 0

                _logger.info(f"extraordinary_leave_hours: {extraordinary_leave_hours}")
                _logger.info(f"working_day_overtime: {working_day_overtime}")

                # Subtract extraordinary leave hours from overtime
                sum_overtime = working_day_overtime - extraordinary_leave_hours
                _logger.info(f"sum_overtime: {sum_overtime}")
                record.sum_overtime_working_day = sum_overtime
                record.overtime_working_day = max(0.0, sum_overtime)
                _logger.info(f"overtime_working_day: {record.overtime_working_day}")
            else:
                record.overtime_working_day = 0.0
                record.sum_overtime_working_day = 0.0


    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration", "sum_overtime_working_day")
    def compute_overtime_weekend(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                contract_start_date, contract_start_datetime = record._get_contract_start_bounds()
                dashboard_start_date = record.dashboard_id.datetime_start.date()
                effective_start_date = contract_start_date if contract_start_date and contract_start_date > dashboard_start_date else dashboard_start_date
                dashboard_start_datetime = record.dashboard_id.datetime_start
                effective_start_datetime = (
                    contract_start_datetime
                    if contract_start_datetime and contract_start_datetime > dashboard_start_datetime
                    else dashboard_start_datetime
                )
                weekend_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", effective_start_date),
                            ("date", "<=", record.dashboard_id.datetime_end.date()),
                            ("day_type", "=", "weekend"),
                        ]
                    )
                    .mapped("date")
                )

                work_logs = self.env["kojto.hr.time.tracking"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("datetime_start", ">=", effective_start_datetime),
                        ("datetime_end", "<=", record.dashboard_id.datetime_end),
                    ]
                )

                weekend_overtime = sum(log.total_hours for log in work_logs if log.datetime_start.date() in weekend_days)

                # Subtract sum_overtime_working_day if it is negative
                sum_overtime_working_day = getattr(record, 'sum_overtime_working_day', 0.0)
                if sum_overtime_working_day < 0:
                    sum_overtime = weekend_overtime + sum_overtime_working_day  # sum_overtime_working_day is negative
                else:
                    sum_overtime = weekend_overtime
                record.sum_overtime_weekend = sum_overtime
                record.overtime_weekend = max(0.0, sum_overtime)
            else:
                record.overtime_weekend = 0.0
                record.sum_overtime_weekend = 0.0

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration", "sum_overtime_weekend")
    def compute_overtime_public_holiday(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                contract_start_date, contract_start_datetime = record._get_contract_start_bounds()
                dashboard_start_date = record.dashboard_id.datetime_start.date()
                effective_start_date = contract_start_date if contract_start_date and contract_start_date > dashboard_start_date else dashboard_start_date
                dashboard_start_datetime = record.dashboard_id.datetime_start
                effective_start_datetime = (
                    contract_start_datetime
                    if contract_start_datetime and contract_start_datetime > dashboard_start_datetime
                    else dashboard_start_datetime
                )
                public_holiday_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", effective_start_date),
                            ("date", "<=", record.dashboard_id.datetime_end.date()),
                            ("day_type", "=", "public_holiday"),
                        ]
                    )
                    .mapped("date")
                )

                work_logs = self.env["kojto.hr.time.tracking"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("datetime_start", ">=", effective_start_datetime),
                        ("datetime_end", "<=", record.dashboard_id.datetime_end),
                    ]
                )

                public_holiday_overtime = sum(log.total_hours for log in work_logs if log.datetime_start.date() in public_holiday_days)

                # Subtract sum_overtime_weekend if it is negative
                sum_overtime_weekend = getattr(record, 'sum_overtime_weekend', 0.0)
                if sum_overtime_weekend < 0:
                    sum_overtime = public_holiday_overtime + sum_overtime_weekend  # sum_overtime_weekend is negative
                else:
                    sum_overtime = public_holiday_overtime
                record.sum_overtime_holiday = sum_overtime
                record.overtime_public_holiday = max(0.0, sum_overtime)
            else:
                record.overtime_public_holiday = 0.0
                record.sum_overtime_holiday = 0.0

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration")
    def compute_hours_leave_paid(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                dashboard_start_date = record.dashboard_id.datetime_start.date()
                dashboard_end_date = record.dashboard_id.datetime_end.date()
                paid_leaves = self.env["kojto.hr.leave.management"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("leave_type_id.leave_group", "=", "paid"),
                        ("leave_status", "!=", "denied"),
                        ("date_start", "<=", dashboard_end_date),
                        ("date_end", ">=", dashboard_start_date),
                    ]
                )
                # Exclude leaves with 'extraordinary' in their name (case-insensitive)
                paid_leaves = paid_leaves.filtered(lambda l: "извънредни" not in (l.leave_type_id.name or '').lower())
                non_working_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", dashboard_start_date),
                            ("date", "<=", dashboard_end_date),
                            ("is_working_day", "=", False),
                        ]
                    )
                    .mapped("date")
                )

                paid_leave_hours = 0
                for paid_leave in paid_leaves:
                    from_date = max(dashboard_start_date, paid_leave.date_start)
                    to_date = min(dashboard_end_date, paid_leave.date_end)
                    days_total = sum(1 for dt in (from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)) if dt.weekday() not in (5, 6) and dt not in non_working_days)
                    paid_leave_hours += days_total * record.work_day_duration
                record.paid_leave = paid_leave_hours
            else:
                record.paid_leave = 0.0

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration")
    def compute_hours_leave_unpaid(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                dashboard_start_date = record.dashboard_id.datetime_start.date()
                dashboard_end_date = record.dashboard_id.datetime_end.date()
                unpaid_leaves = self.env["kojto.hr.leave.management"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("leave_type_id.leave_group", "=", "unpaid"),
                        ("leave_status", "!=", "denied"),
                        ("date_start", "<=", dashboard_end_date),
                        ("date_end", ">=", dashboard_start_date),
                    ]
                )
                unpaid_leave_hours = 0
                non_working_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", dashboard_start_date),
                            ("date", "<=", dashboard_end_date),
                            ("is_working_day", "=", False),
                        ]
                    )
                    .mapped("date")
                )

                for unpaid_leave in unpaid_leaves:
                    from_date = max(dashboard_start_date, unpaid_leave.date_start)
                    to_date = min(dashboard_end_date, unpaid_leave.date_end)
                    days_total = sum(1 for dt in (from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)) if dt.weekday() not in (5, 6) and dt not in non_working_days)
                    unpaid_leave_hours += days_total * record.work_day_duration
                record.unpaid_leave = unpaid_leave_hours
            else:
                record.unpaid_leave = 0.0

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration")
    def compute_hours_leave_sick(self):
        for record in self:
            if record.dashboard_id and record.dashboard_id.datetime_start and record.dashboard_id.datetime_end:
                dashboard_start_date = record.dashboard_id.datetime_start.date()
                dashboard_end_date = record.dashboard_id.datetime_end.date()
                sick_leaves = self.env["kojto.hr.leave.management"].search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("leave_type_id.leave_group", "=", "sick"),
                        ("leave_status", "!=", "denied"),
                        ("date_start", "<=", dashboard_end_date),
                        ("date_end", ">=", dashboard_start_date),
                    ]
                )
                sick_leave_hours = 0

                non_working_days = (
                    self.env["kojto.hr.working.days"]
                    .search(
                        [
                            ("date", ">=", dashboard_start_date),
                            ("date", "<=", dashboard_end_date),
                            ("is_working_day", "=", False),
                        ]
                    )
                    .mapped("date")
                )

                for sick_leave in sick_leaves:
                    from_date = max(dashboard_start_date, sick_leave.date_start)
                    to_date = min(dashboard_end_date, sick_leave.date_end)
                    days_total = sum(1 for dt in (from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)) if dt.weekday() not in (5, 6) and dt not in non_working_days)
                    sick_leave_hours += days_total * record.work_day_duration
                record.sick_leave = sick_leave_hours
            else:
                record.sick_leave = 0.0

    @api.depends("norm", "workhours")
    def compute_balance(self):
        for record in self:
            record.balance = record.total - record.norm # this is equal to sum_overtime_holiday

    @api.depends("paid_leave", "unpaid_leave", "sick_leave", "workhours")
    def compute_total(self):
        for record in self:
            record.total = record.workhours + record.paid_leave + record.unpaid_leave + record.sick_leave

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end")
    def compute_workhours(self):
        for record in self:
            work_hours_list = self.env["kojto.hr.time.tracking"].search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("datetime_start", ">=", record.dashboard_id.datetime_start),
                    ("datetime_end", "<=", record.dashboard_id.datetime_end),
                ]
            )
            total_workhours = 0
            # Get all 'extraordinary' paid leaves for this employee in the dashboard period
            dashboard_start_date = record.dashboard_id.datetime_start.date() if record.dashboard_id.datetime_start else None
            dashboard_end_date = record.dashboard_id.datetime_end.date() if record.dashboard_id.datetime_end else None
            if dashboard_start_date and dashboard_end_date:
                extraordinary_leaves = self.env["kojto.hr.leave.management"].search([
                    ("employee_id", "=", record.employee_id.id),
                    ("leave_type_id.leave_group", "=", "paid"),
                    ("leave_status", "!=", "denied"),
                    ("date_start", "<=", dashboard_end_date),
                    ("date_end", ">=", dashboard_start_date),
                ])
                extraordinary_leaves = extraordinary_leaves.filtered(lambda l: "извънредни" in (l.leave_type_id.name or '').lower())

                def get_overlap_hours(wh_start, wh_end, leave_start_date, leave_end_date):
                    # Convert leave dates to datetime for comparison with workhour datetimes
                    leave_start_dt = datetime.combine(leave_start_date, datetime.min.time())
                    leave_end_dt = datetime.combine(leave_end_date, datetime.max.time())
                    latest_start = max(wh_start, leave_start_dt)
                    earliest_end = min(wh_end, leave_end_dt)
                    delta = (earliest_end - latest_start).total_seconds() / 3600.0
                    return max(0, delta)

                for workhour in work_hours_list:
                    wh_start = workhour.datetime_start
                    wh_end = workhour.datetime_end
                    wh_total = workhour.total_hours
                    overlap_hours = 0
                    for leave in extraordinary_leaves:
                        overlap = get_overlap_hours(wh_start, wh_end, leave.date_start, leave.date_end)
                        overlap_hours += overlap
                    # Subtract overlap hours from this workhour record
                    total_workhours += max(0, wh_total - overlap_hours)
            record.workhours = total_workhours

    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end", "work_day_duration")
    def compute_norm(self):
        for record in self:
            if record.dashboard_id:
                from_date, to_date = record.convert_timezone_dashboard_dates()

                # Fetch all contracts overlapping the dashboard period, including ongoing ones
                dashboard_start_dt = record.dashboard_id.datetime_start
                dashboard_end_dt = record.dashboard_id.datetime_end
                if not dashboard_start_dt or not dashboard_end_dt:
                    record.norm = 0.0
                    continue

                dashboard_start_date = dashboard_start_dt.date()
                dashboard_end_date = dashboard_end_dt.date()

                contracts = record.env["kojto.hr.employees.contracts"].search([
                    ("employee_id", "=", record.employee_id.id),
                    ("date_start", "<=", dashboard_end_date),
                    "|",
                    ("date_end", ">=", dashboard_start_date),
                    ("date_end", "=", False),
                ], order="date_start asc")

                if not contracts:
                    record.norm = 0.0
                    continue

                # Get all working days in the dashboard period
                working_days = record.env["kojto.hr.working.days"].search([
                    ("date", ">=", from_date),
                    ("date", "<=", to_date),
                    ("is_working_day", "=", True),
                ]).mapped("date")

                # Sum expected hours per working day based on the applicable contract
                total_expected_hours = 0.0
                for day in working_days:
                    applicable = False
                    applicable_duration = 0.0
                    # pick the latest-starting contract that covers this day
                    for contract in contracts:
                        start_date = contract.date_start
                        end_date = contract.date_end
                        if start_date and start_date <= day and (not end_date or end_date >= day):
                            applicable = True
                            applicable_duration = contract.work_day_duration or 0.0
                    if applicable:
                        total_expected_hours += applicable_duration

                record.norm = total_expected_hours
            else:
                record.norm = 0.0

    @api.depends("employee_id", "dashboard_id.datetime_start")
    def compute_work_day_duration(self):
        for record in self:
            dashboard_start_dt = record.dashboard_id.datetime_start
            dashboard_end_dt = record.dashboard_id.datetime_end
            if not dashboard_start_dt or not dashboard_end_dt or not record.employee_id:
                record.work_day_duration = 0.0
                continue

            dashboard_start_date = dashboard_start_dt.date()
            dashboard_end_date = dashboard_end_dt.date()

            contract = record.env["kojto.hr.employees.contracts"].search([
                ("employee_id", "=", record.employee_id.id),
                ("date_start", "<=", dashboard_end_date),
                "|",
                ("date_end", ">=", dashboard_start_date),
                ("date_end", "=", False),
            ], order="date_start desc", limit=1)
            record.work_day_duration = contract.work_day_duration if contract else 0.0


    @api.depends("employee_id", "dashboard_id.datetime_start", "dashboard_id.datetime_end")
    def compute_no_record_days(self):
        for record in self:
            if not record.employee_id or not record.dashboard_id:
                record.no_record_days = 0
                continue

            start_date, end_date = record.convert_timezone_dashboard_dates()

            # Get the employee's contract for this period
            dashboard_start_dt = record.dashboard_id.datetime_start
            dashboard_end_dt = record.dashboard_id.datetime_end
            if not dashboard_start_dt or not dashboard_end_dt:
                record.no_record_days = 0
                continue

            dashboard_start_date = dashboard_start_dt.date()
            dashboard_end_date = dashboard_end_dt.date()

            contract = record.env["kojto.hr.employees.contracts"].search([
                ("employee_id", "=", record.employee_id.id),
                ("date_start", "<=", dashboard_end_date),
                "|",
                ("date_end", ">=", dashboard_start_date),
                ("date_end", "=", False),
            ], order="date_start desc", limit=1)

            # Determine the effective start date for counting no-record days
            effective_start_date = start_date
            if contract and contract.date_start:
                contract_start_date = contract.date_start
                if contract_start_date > start_date:
                    effective_start_date = contract_start_date

            # Get all working days in the period from the effective start date
            working_days = self.env["kojto.hr.working.days"].search([
                ("date", ">=", effective_start_date),
                ("date", "<=", end_date),
                ("is_working_day", "=", True),
            ]).mapped("date")

            _logger.info("working_days: %s", working_days)

            # Get days with work hours records
            work_hours_days = set()
            try:
                work_hours_records = self.env["kojto.hr.time.tracking"].search([
                    ("employee_id", "=", record.employee_id.id),
                    ("datetime_start", ">=", effective_start_date),
                    ("datetime_end", "<=", end_date),
                ])
                # Extract dates from datetime_start
                work_hours_days = set(rec.datetime_start.date() for rec in work_hours_records if rec.datetime_start)
            except Exception:
                # Model doesn't exist or other error
                pass

            _logger.info("work_hours_days: %s", work_hours_days)

            # Get days with leave records
            leave_days = set()
            try:
                leave_records = self.env["kojto.hr.leave.management"].search([
                    ("employee_id", "=", record.employee_id.id),
                    ("date_start", "<=", end_date),
                    ("date_end", ">=", effective_start_date),
                ])
                for rec in leave_records:
                    if rec.date_start and rec.date_end:
                        current_date = rec.date_start
                        leave_end_date = rec.date_end
                        while current_date <= leave_end_date:
                            leave_days.add(current_date)
                            current_date += timedelta(days=1)

            except Exception:
                # Model doesn't exist or other error
                pass

            _logger.info("leave_days: %s", leave_days)

            # Days with any kind of record (work hours or leave days)
            recorded_days = work_hours_days.union(leave_days)
            _logger.info("recorded_days: %s", recorded_days)

            # Count working days without any records
            no_record_days = 0
            for working_day in working_days:
                if working_day not in recorded_days:
                    no_record_days += 1

            record.no_record_days = no_record_days
