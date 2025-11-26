from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime, time, timedelta
import logging

_logger = logging.getLogger(__name__)


class KojtoHrLeaveManagement(models.Model):
    _name = "kojto.hr.leave.management"
    _description = "Kojto Hr Leave Management"
    _order = "date_start desc"
    _inherit = ["kojto.library.printable"]

    name = fields.Char(string="Number", compute="compute_number", store="True")
    employee_id = fields.Many2one("kojto.hr.employees", default=lambda self: self.get_current_employee(), string="Employee", required=True, index=True)
    user_id = fields.Many2one(related="employee_id.user_id", string="Associated User")
    leave_type_id = fields.Many2one("kojto.hr.leave.type", string="Leave type", required=True, domain=[('active', '=', True)], ondelete='restrict')

    reason = fields.Char(string="Reason")
    date_start = fields.Date(string="From", required=True, index=True, default=fields.Date.today)
    date_end = fields.Date(string="To", required=True, index=True, default=fields.Date.today)
    leave_status = fields.Selection(selection=[("approved", "Approved"), ("denied", "Denied"), ("pending", "Pending")], string="Status", default="pending", required=True, copy=False)

    # Fields for printing
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_bg").id, required=True)
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment")

    # Additional fields for leave order
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True)
    approved_date = fields.Datetime(string="Approval Date", readonly=True)
    leave_order_number = fields.Char(string="Leave Order Number", compute="compute_leave_order_number")
    leave_duration = fields.Integer(string="Duration", compute="compute_leave_duration")

    leave_is_printable = fields.Boolean(string="Leave is Printable", compute="_compute_leave_is_printable")

    @api.model
    def create(self, vals):
        # If vals is a list, process each dict in the list
        if isinstance(vals, list):
            for val in vals:
                val['leave_status'] = 'pending'
            created_records = super().create(vals)
            # Notify users about past month events
            for record in created_records:
                record.sudo()._notify_users_about_past_events("created")
            return created_records
        # If vals is a dict, process as usual
        vals['leave_status'] = 'pending'
        created_record = super().create(vals)
        # Notify users about past month events
        created_record.sudo()._notify_users_about_past_events("created")
        return created_record


    def write(self, vals):
        # Ensure leave_status field has a valid value when updating
        if 'leave_status' in vals and not vals['leave_status']:
            vals['leave_status'] = 'pending'
        result = super().write(vals)

        # Notify users about past month events
        for record in self:
            record.sudo()._notify_users_about_past_events("updated")

        return result

    def unlink(self):
        return super(KojtoHrLeaveManagement, self).unlink()

    @api.model
    def get_current_employee(self):
        user_id = self.env.user.id
        employee = self.env["kojto.hr.employees"].search([("user_id", "=", user_id)], limit=1)
        return employee.id if employee else False

    @api.constrains("employee_id","date_start", "date_end", "leave_type_id")
    def check_dates(self):
        for record in self:
            if record.date_end < record.date_start:
                raise ValidationError("Invalid dates.")

            if record.leave_status in ["approved", "denied"]:
                raise ValidationError("You cannot edit already approved or denied leaves")

            overlapping_leaves = self.search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("id", "!=", record.id),
                    ("date_start", "<=", record.date_end),
                    ("date_end", ">=", record.date_start),
                    ("leave_status", "!=", "denied"),
                ]
            )
            if overlapping_leaves:
                raise ValidationError("You already have taken leave for this period.")

            overlapping_with_workhours = self.env["kojto.hr.time.tracking"].search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("datetime_start", "<=", fields.Datetime.to_string(datetime.combine(record.date_end, time.max))),
                    ("datetime_end", ">=", fields.Datetime.to_string(datetime.combine(record.date_start, time.min))),
                ]
            )
            if overlapping_with_workhours:
                raise ValidationError("You have recorded work hours for this period.")

            overlapping_trips = self.env["kojto.hr.business.trips"].search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("date_start", "<=", record.date_end),
                    ("date_end", ">=", record.date_start),
                ]
            )
            if overlapping_trips:
                raise ValidationError("You have been on a business trip in this period.")

    @api.depends("employee_id")
    def compute_number(self):
        for record in self:
            if not record.employee_id:
                number_leave = 0
                continue
            last_record = len(self.search([("employee_id", "=", record.employee_id.id), ("id", "!=", record.id)]))
            if last_record:
                number_leave = last_record + 1
            else:
                number_leave = 1
            length = len(str(number_leave))
            record.name = "LV." + str(record.employee_id.id) + "." + (3 - length) * "0" + str(number_leave)

    @api.depends("employee_id", "date_start")
    def compute_leave_order_number(self):
        for record in self:
            if record.employee_id and record.date_start:
                year = record.date_start.year
                month = record.date_start.month
                record.leave_order_number = f"LO.{record.employee_id.id}.{year}.{month:02d}"
            else:
                record.leave_order_number = False

    def approve_leaves(self):
        for record in self:
            if record.leave_status == "pending":
                record.leave_status = "approved"
                record.approved_by = self.env.user.id
                record.approved_date = datetime.now()

    def refuse_leaves(self):
        for record in self:
            if record.leave_status == "pending":
                record.leave_status = "denied"
                record.approved_by = self.env.user.id
                record.approved_date = datetime.now()

    @api.ondelete(at_uninstall=False)
    def check_dates_before_unlink(self):
        # Allow administrators to delete without restrictions
        if self.env.user.has_group('kojto_base.kojto_administrator'):
            return
        today = datetime.today()
        current_month = today.month
        current_year = today.year
        for record in self:
            if record.date_start:
                if (record.date_start.year < current_year or (record.date_start.year == current_year and record.date_start.month < current_month)) or (record.date_end.year < current_year or (record.date_end.year == current_year and record.date_end.month < current_month)):
                    raise ValidationError("You cannot delete leaves from the previous month.")

            if record.leave_status in ["approved", "denied"]:
                raise ValidationError("You cannot delete leaves that are already approved or denied.")

    @api.model
    def fix_data_inconsistencies(self):
        """Fix any data inconsistencies that might cause SelectionField errors"""
        try:
            _logger.info("Starting data inconsistency fix for leave management")

            # Fix records with missing leave_status
            records_without_status = self.search([('leave_status', '=', False)])
            if records_without_status:
                records_without_status.write({'leave_status': 'pending'})
                _logger.info("Fixed %s records with missing leave_status", len(records_without_status))

            # Fix records with NULL leave_status (different from False)
            records_with_null_status = self.search([('leave_status', '=', None)])
            if records_with_null_status:
                records_with_null_status.write({'leave_status': 'pending'})
                _logger.info("Fixed %s records with NULL leave_status", len(records_with_null_status))

            # Fix records with invalid leave_status values
            valid_statuses = ['approved', 'denied', 'pending']
            all_records = self.search([])
            invalid_status_records = []

            for record in all_records:
                if record.leave_status not in valid_statuses:
                    invalid_status_records.append(record.id)

            if invalid_status_records:
                invalid_records = self.browse(invalid_status_records)
                invalid_records.write({'leave_status': 'pending'})
                _logger.info("Fixed %s records with invalid leave_status values", len(invalid_status_records))

            # Ensure all records have valid leave_type_id
            records_without_type = self.search([('leave_type_id', '=', False)])
            if records_without_type:
                # Get the first available leave type
                first_leave_type = self.env['kojto.hr.leave.type'].search([], limit=1)
                if first_leave_type:
                    records_without_type.write({'leave_type_id': first_leave_type.id})
                    _logger.info("Fixed %s records with missing leave_type_id", len(records_without_type))
                else:
                    _logger.error("No leave types available to fix records")

            # Fix records with NULL leave_type_id
            records_with_null_type = self.search([('leave_type_id', '=', None)])
            if records_with_null_type:
                first_leave_type = self.env['kojto.hr.leave.type'].search([], limit=1)
                if first_leave_type:
                    records_with_null_type.write({'leave_type_id': first_leave_type.id})
                    _logger.info("Fixed %s records with NULL leave_type_id", len(records_with_null_type))

            _logger.info("Data inconsistency fix completed")

        except Exception as e:
            _logger.error("Error fixing data inconsistencies: %s", e)
            raise ValidationError(f"Data fix failed: {e}")

    @api.depends('date_start', 'date_end')
    def compute_leave_duration(self):
        for record in self:
            if not record.date_start or not record.date_end:
                record.leave_duration = 0
                continue

            if record.date_end < record.date_start:
                record.leave_duration = 0
                continue

            working_days = self.env['kojto.hr.working.days'].search([
                ('date', '>=', record.date_start),
                ('date', '<=', record.date_end),
                ('is_working_day', '=', True)
            ])

            if not working_days:
                duration = 0
                current_date = record.date_start
                while current_date <= record.date_end:
                    # Monday = 0, Sunday = 6
                    if current_date.weekday() < 5:  # Monday to Friday
                        duration += 1
                    current_date += timedelta(days=1)
                record.leave_duration = duration
            else:
                record.leave_duration = len(working_days)

    def print_document(self):
        """Print leave request document"""
        self.ensure_one()
        return self.with_context(
            report_ref="kojto_hr.report_kojto_hr_leave_management",
            force_report_ref=True
        ).print_document_as_pdf()

    def generate_leave_pdf_attachment(self):
        """Generate and attach PDF to the record"""
        self.ensure_one()
        try:
            pdf_action = self.with_context(
                report_ref="kojto_hr.report_kojto_hr_leave_management",
                force_report_ref=True
            ).print_document_as_pdf()

            # Get the generated PDF content
            if pdf_action and pdf_action.get('type') == 'ir.actions.act_url':
                attachment_id = int(pdf_action['url'].split('/')[-1].split('?')[0])
                attachment = self.env['ir.attachment'].browse(attachment_id)

                # Update the record with the attachment
                self.write({
                    'pdf_attachment_id': attachment.id
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'PDF attachment generated successfully',
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error("Error generating PDF attachment: %s", e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to generate PDF: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    @api.depends('leave_status')
    def _compute_leave_is_printable(self):
        for record in self:
            record.leave_is_printable = record.leave_status == 'approved'

    def get_employee_name_for_printing(self):
        """Get employee name based on the leave's language"""
        self.ensure_one()
        if self.employee_id and self.language_id:
            # First try to find a name in the leave's language
            name_record = self.env['kojto.base.names'].search([
                ('employee_id', '=', self.employee_id.id),
                ('language_id', '=', self.language_id.id),
                ('active', '=', True)
            ], limit=1)

            if name_record:
                return name_record.name
            else:
                # Fallback to the employee's default name
                return self.employee_id.name
        elif self.employee_id:
            # If no language specified, use default name
            return self.employee_id.name
        else:
            return ""

    def get_employee_position_for_printing(self):
        """Return the employee position from the contract that matches the leave date.

        Priority: contract covering date_start; if none, latest contract before date_start;
        fallback: employee's current position field if available; otherwise empty string.
        """
        self.ensure_one()
        if not self.employee_id or not self.date_start:
            return ""

        Contracts = self.env["kojto.hr.employees.contracts"]
        leave_start = self.date_start

        # 1) Contract covering the start moment
        covering_contract = Contracts.search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", "<=", leave_start),
            "|",
            ("date_end", ">=", leave_start),
            ("date_end", "=", False),
        ], order="date_start desc", limit=1)
        if covering_contract and covering_contract.position:
            return covering_contract.position

        # 2) Latest contract before start
        previous_contract = Contracts.search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", "<=", leave_start),
        ], order="date_start desc", limit=1)
        if previous_contract and previous_contract.position:
            return previous_contract.position

        # 3) Fallback to employee field if exists
        if "position" in self.employee_id._fields and self.employee_id.position:
            return self.employee_id.position

        return ""


    @api.constrains('date_start')
    def _check_date_start_by_user_group(self):
        for record in self:
            if not record.date_start:
                continue

            current_user = self.env.user
            record_date = record.date_start
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
                        f"You can only create or edit leaves for the current and previous month.\n"
                        f"The earliest date allowed is: {previous_month_start.strftime('%d.%m.%Y')}"
                    )

            # All other groups - only future leaves from tomorrow onwards
            # Automatically applied to any user who is NOT an Administrator, HR or Assistant
            else:
                tomorrow_date = (datetime.now() + timedelta(days=1)).date()
                if record_date < tomorrow_date:
                    raise ValidationError(
                        f"You can only create or edit leaves starting from tomorrow.\n"
                        f"The earliest date allowed is: {tomorrow_date.strftime('%d.%m.%Y')}"
                    )


    def _notify_users_about_past_events(self, action):
        """Notify HR users about past leave events"""
        try:
             current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
             past_events = self.filtered(lambda e: e.date_start and e.date_start < current_month_start)

             if not past_events:
                 return

             notification_group = self.env.ref('kojto_base.kojto_hr', raise_if_not_found=False)
             if not notification_group:
                 _logger.warning("HR group 'kojto_base.kojto_hr' not found")
                 return

             hr_users = self.env['res.users'].search([
                    ('group_ids', 'in', [notification_group.id]),
                    ('active', '=', True),
                    ('email', '!=', False)
            ])

             if not hr_users:
                 _logger.warning("No active HR users with email found")
                 return

             _logger.info(f"Found {len(hr_users)} HR users to notify for leave events")

             for event in past_events:
                 self._send_past_event_notification_email(event, hr_users, action)

        except Exception as e:
             _logger.error(f"Error in leave management notifications: {e}")
        pass

    def _send_past_event_notification_email(self, event, users_to_notify, action):
        """Send email notification about past event to users"""
        try:
            subject = f"HR Notification: {action.title()} Leave Event"

            body = f"""
            <p>A leave event has been {action} in the past month:</p>
            <ul>
                <li><strong>Employee:</strong> {event.employee_id.name if event.employee_id else 'N/A'}</li>
                <li><strong>Start:</strong> {event.date_start.strftime('%Y-%m-%d') if event.date_start else 'N/A'}</li>
                <li><strong>End:</strong> {event.date_end.strftime('%Y-%m-%d') if event.date_end else 'N/A'}</li>
                <li><strong>Leave Type:</strong> {event.leave_type_id.name if event.leave_type_id else 'N/A'}</li>
                <li><strong>Days:</strong> {event.leave_duration}</li>
                <li><strong>Comment:</strong> {event.reason or 'N/A'}</li>
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


