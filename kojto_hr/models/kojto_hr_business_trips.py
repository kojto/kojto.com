from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, date
import uuid
import logging

_logger = logging.getLogger(__name__)


class KojtoHrBusinessTrips(models.Model):
    _name = "kojto.hr.business.trips"
    _description = "Kojto Hr Business Trips"
    _inherit = ["kojto.library.printable"]
    _order = "date_start desc"
    _report_ref = "kojto_hr.report_kojto_hr_business_trips"

    name = fields.Char(string="Trip name", compute="compute_trip_name", store=True)
    code_id = fields.Many2one("kojto.commission.codes", string="Code")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.BGN").id)

    # Company Information
    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True)
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document", required=True)
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address", required=True)
    company_registration_number = fields.Char(related="company_id.registration_number", string="Registration Number")

    # Employee fields
    employee_id = fields.Many2one("kojto.hr.employees", default=lambda self: self.get_current_employee(), string="Employee", required=True, index=True)
    user_id = fields.Many2one(related="employee_id.user_id", string="Associated User")
    destination = fields.Char(string="Destination", translate=True)
    business_purpose = fields.Char(string="Business Purpose", translate=True)
    date_start = fields.Date(string="From", required=True, index=True, default=fields.Date.today)
    date_end = fields.Date(string="To", required=True, index=True, default=fields.Date.today)
    date_issued = fields.Date(string="Issued on", required=True, index=True, default=fields.Date.today)
    duration_days = fields.Integer(string="Duration (Days)", compute="_compute_duration_days", help="Calendar days including from and to days")
    content_ids = fields.One2many("kojto.hr.business.trip.contents", "trip_id", string="Contents")
    content_is_actual_expense = fields.One2many("kojto.hr.business.trip.contents", "trip_id", string="Actual Expenses", domain=[("is_actual_expense", "=", True)])
    content_not_actual_expense = fields.One2many("kojto.hr.business.trip.contents", "trip_id", string="Budget Expenses", domain=[("is_actual_expense", "=", False)])
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment", copy=False)

    # Computed fields for expense totals in business trip currency
    total_budget_expenses_trip_currency = fields.Float(string="Total Budget Expenses (Trip Currency)", compute="_compute_total_expenses_trip_currency", digits=(15, 2))
    total_actual_expenses_trip_currency = fields.Float(string="Total Actual Expenses (Trip Currency)", compute="_compute_total_expenses_trip_currency", digits=(15, 2))
    total_payable_to_employee_trip_currency = fields.Float(string="Total Payable to Employee (Trip Currency)", compute="_compute_total_expenses_trip_currency", digits=(15, 2))
    total_paid_to_employee_trip_currency = fields.Float(string="Total Paid to Employee (Trip Currency)", compute="_compute_total_paid_to_employee_trip_currency", digits=(15, 2))

    # Balance field showing difference between actual expenses payable to employee and payments to employee
    balance_trip_currency = fields.Float(string="Balance (Trip Currency)", compute="_compute_balance", digits=(15, 2), help="Positive value means employee must be paid, negative value means employee must return money")

    # Computed fields for report calculations
    total_distance_km = fields.Float(string="Total Distance (km)", compute="_compute_total_distance_km", store=False, digits=(10, 2))
    total_personal_km = fields.Float(string="Total Personal Distance (km)", compute="_compute_total_personal_km", store=False, digits=(10, 2))

    description = fields.Text(string="Description")
    logbook_ids = fields.One2many('kojto.hr.business.trip.logbook', 'trip_id', string='Logbook Entries')
    payment_ids = fields.One2many('kojto.hr.business.trip.payments', 'trip_id', string='Payments to Employee')

    @api.model
    def get_current_employee(self):
        user_id = self.env.user.id
        employee = self.env["kojto.hr.employees"].search([("user_id", "=", user_id)], limit=1)
        return employee.id if employee else False

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    @api.onchange("company_id")
    def onchange_company(self):
        fields_to_reset = {
            "company_name_id": "company_id",
            "company_address_id": "company_id",
        }

        for field, id_field in fields_to_reset.items():
            setattr(self, field, False)

        if self.company_id:
            company = self.company_id
            for model, field in [
                ("kojto.base.names", "company_name_id"),
                ("kojto.base.addresses", "company_address_id"),
            ]:
                record = self.env[model].search([("contact_id", "=", company.id), ("active", "=", True)], limit=1)
                if record:
                    setattr(self, field, record.id)

    def _get_next_total_trip_number(self):
        """Get the next total trip number by finding the highest number after '/' and adding 1"""
        # Get all existing business trips with names
        existing_trips = self.search([("name", "!=", False), ("name", "!=", "")])

        max_number = 0
        for trip in existing_trips:
            if trip.name and '/' in trip.name:
                # Extract number after the last '/'
                parts = trip.name.split('/')
                if len(parts) >= 2:
                    try:
                        # Get the last part after '/' and extract only digits
                        number_part = parts[-1]
                        number_part = ''.join(filter(str.isdigit, number_part))
                        if number_part:
                            trip_number = int(number_part)
                            max_number = max(max_number, trip_number)
                    except (ValueError, IndexError):
                        continue

        return max_number + 1

    @api.depends("employee_id", "code_id")
    def compute_trip_name(self):
        for record in self:
            if record.code_id and record.employee_id:
                maincode = record.code_id.maincode_id.maincode if record.code_id.maincode_id else ""
                code = record.code_id.code if record.code_id.code else ""

                # Count existing trips for this code (excluding current record if it has an ID)
                existing_trips_for_code = self.search([("code_id", "=", record.code_id.id)])
                if record.id:
                    existing_trips_for_code = existing_trips_for_code.filtered(lambda x: x.id != record.id)
                code_number_trip = len(existing_trips_for_code)

                # Get the next total trip number from existing names
                next_total_number = self._get_next_total_trip_number()

                record.name = f"{maincode}.{code}.BT.{str(code_number_trip + 1).zfill(3)}/{next_total_number}"
            else:
                record.name = ""

    @api.depends('date_start', 'date_end')
    def _compute_duration_days(self):
        """Compute duration in calendar days including from and to days"""
        for record in self:
            if record.date_start and record.date_end:
                # Calculate the difference in days and add 1 to include both start and end days
                delta = record.date_end - record.date_start
                record.duration_days = delta.days + 1
            else:
                record.duration_days = 0

    def print_business_trip_order(self):
        """Print Business Trip Order"""
        self.ensure_one()
        return self.with_context(
            report_ref="kojto_hr.report_kojto_hr_business_trip_order",
            force_report_ref=True,
            lang=self.language_id.code if self.language_id else 'en_US'
        ).print_document_as_pdf()

    def print_business_trip_report(self):
        """Print Business Trip Report"""
        self.ensure_one()
        return self.with_context(
            report_ref="kojto_hr.report_kojto_hr_business_trips",
            force_report_ref=True,
            lang=self.language_id.code if self.language_id else 'en_US'
        ).print_document_as_pdf()

    def copy_business_trip_contents(self):
        """Copy expenses from current business trip to a new one"""
        self.ensure_one()

        # Create a new business trip with the same basic information
        new_trip_vals = {
            'employee_id': self.employee_id.id,
            'code_id': self.code_id.id,
            'company_id': self.company_id.id if self.company_id else False,
            'company_name_id': self.company_name_id.id if self.company_name_id else False,
            'company_address_id': self.company_address_id.id if self.company_address_id else False,
            'destination': self.destination,
            'business_purpose': self.business_purpose,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'language_id': self.language_id.id,
            'currency_id': self.currency_id.id,
        }

        # Create the new business trip
        new_trip = self.create(new_trip_vals)

        # Copy all expenses from the current trip to the new trip
        for expense in self.content_ids:
            expense_vals = {
                'trip_id': new_trip.id,
                'expense': expense.expense,
                'total_sum': expense.total_sum,
                'currency_id': expense.currency_id.id if expense.currency_id else False,
                'trip_group': expense.trip_group,
                'trip_type': expense.trip_type,
            }
            self.env['kojto.hr.business.trip.contents'].create(expense_vals)

        # Return action to open the new business trip form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trips',
            'res_id': new_trip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def copy_business_trip(self):
        """Copy entire business trip with all contents, logbook entries, and payments"""
        self.ensure_one()

        # Create a new business trip with the same basic information
        new_trip_vals = {
            'employee_id': self.employee_id.id,
            'code_id': self.code_id.id,
            'company_id': self.company_id.id if self.company_id else False,
            'company_name_id': self.company_name_id.id if self.company_name_id else False,
            'company_address_id': self.company_address_id.id if self.company_address_id else False,
            'destination': self.destination,
            'business_purpose': self.business_purpose,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'language_id': self.language_id.id,
            'currency_id': self.currency_id.id,
            'description': self.description,
        }

        # Create the new business trip
        new_trip = self.create(new_trip_vals)

        # Copy all expenses from the current trip to the new trip
        for expense in self.content_ids:
            expense_vals = {
                'trip_id': new_trip.id,
                'name': expense.name,
                'quantity': expense.quantity,
                'unit_id': expense.unit_id.id if expense.unit_id else False,
                'unit_price': expense.unit_price,
                'currency_id': expense.currency_id.id if expense.currency_id else False,
                'trip_group': expense.trip_group,
                'is_actual_expense': expense.is_actual_expense,
                'payable_to_employee': expense.payable_to_employee,
            }
            self.env['kojto.hr.business.trip.contents'].create(expense_vals)

        # Copy all logbook entries
        for logbook_entry in self.logbook_ids:
            logbook_vals = {
                'trip_id': new_trip.id,
                'date': logbook_entry.date,
                'is_working_day': logbook_entry.is_working_day,
                'destination': logbook_entry.destination,
                'from_km': logbook_entry.from_km,
                'to_km': logbook_entry.to_km,
                'personal_km': logbook_entry.personal_km,
                'comment': logbook_entry.comment,
            }
            self.env['kojto.hr.business.trip.logbook'].create(logbook_vals)

        # Copy all payments
        for payment in self.payment_ids:
            payment_vals = {
                'trip_id': new_trip.id,
                'payment_date': payment.payment_date,
                'description': payment.description,
                'currency_id': payment.currency_id.id if payment.currency_id else False,
                'amount': payment.amount,
            }
            self.env['kojto.hr.business.trip.payments'].create(payment_vals)

        # Return action to open the new business trip form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trips',
            'res_id': new_trip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('content_ids', 'content_ids.total_sum', 'content_ids.currency_id', 'content_ids.is_actual_expense', 'content_ids.payable_to_employee', 'payment_ids', 'payment_ids.amount', 'payment_ids.currency_id', 'date_start')
    def _compute_total_expenses_trip_currency(self):
        """Compute total budget and actual expenses in business trip currency"""
        for record in self:
            total_budget = 0.0
            total_actual = 0.0
            total_payable_to_employee = 0.0

            for expense in record.content_ids:
                if expense.total_sum:
                    # Convert all expenses to business trip currency
                    if expense.currency_id and expense.currency_id != record.currency_id:
                        # Convert using custom exchange rate system
                        exchange_rate = record.get_exchange_rate(expense.currency_id, record.currency_id, record.date_start)
                        converted_amount = expense.total_sum * exchange_rate
                    elif expense.currency_id and expense.currency_id == record.currency_id:
                        # Same currency, no conversion needed
                        converted_amount = expense.total_sum
                    else:
                        # No currency specified, assume it's in business trip currency
                        converted_amount = expense.total_sum

                    if expense.is_actual_expense:
                        total_actual += converted_amount
                        if expense.payable_to_employee:
                            total_payable_to_employee += converted_amount
                    else:
                        total_budget += converted_amount

            record.total_budget_expenses_trip_currency = total_budget
            record.total_actual_expenses_trip_currency = total_actual
            record.total_payable_to_employee_trip_currency = total_payable_to_employee

    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.currency_id')
    def _compute_total_paid_to_employee_trip_currency(self):
        """Compute total payments to employee in business trip currency"""
        for record in self:
            total_payments = 0.0

            # Calculate total payments converted to business trip currency
            for payment in record.payment_ids:
                if payment.amount and payment.currency_id:
                    if payment.currency_id != record.currency_id:
                        # Convert using custom exchange rate system
                        exchange_rate = record.get_exchange_rate(payment.currency_id, record.currency_id, payment.payment_date)
                        converted_amount = payment.amount * exchange_rate
                        total_payments += converted_amount
                    else:
                        total_payments += payment.amount

            record.total_paid_to_employee_trip_currency = total_payments

    @api.depends('total_payable_to_employee_trip_currency', 'total_paid_to_employee_trip_currency')
    def _compute_balance(self):
        """Compute balance: total actual expenses payable to employee - total payments to employee"""
        for record in self:
            total_payable = record.total_payable_to_employee_trip_currency or 0.0
            total_payments = record.total_paid_to_employee_trip_currency or 0.0

            record.balance_trip_currency = total_payable - total_payments

    @api.depends('logbook_ids', 'logbook_ids.distance_km')
    def _compute_total_distance_km(self):
        """Compute total distance from logbook entries"""
        for record in self:
            total_distance = 0.0
            for logbook_entry in record.logbook_ids:
                if logbook_entry.distance_km:
                    total_distance += logbook_entry.distance_km
            record.total_distance_km = total_distance

    @api.depends('logbook_ids', 'logbook_ids.personal_km')
    def _compute_total_personal_km(self):
        """Compute total personal distance from logbook entries"""
        for record in self:
            total_personal = 0.0
            for logbook_entry in record.logbook_ids:
                if logbook_entry.personal_km:
                    total_personal += logbook_entry.personal_km
            record.total_personal_km = total_personal

    def create_budget_expense(self):
        """Create a new budget expense with proper context"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trip.contents',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
                'default_is_actual_expense': False,
            }
        }

    def create_actual_expense(self):
        """Create a new actual expense with proper context"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trip.contents',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
                'default_is_actual_expense': True,
            }
        }

    def get_exchange_rate(self, from_currency, to_currency, date):
        """Get exchange rate using our custom currency exchange system"""
        if from_currency == to_currency:
            return 1.0

        # Convert date to datetime for proper comparison
        if isinstance(date, str):
            from datetime import datetime
            date = datetime.strptime(date, '%Y-%m-%d').date()

        # Convert date to datetime string for database comparison
        date_datetime = fields.Datetime.to_string(fields.Datetime.from_string(f"{date} 00:00:00"))

        # First try direct lookup
        exchange_rate = self.env["kojto.base.currency.exchange"].search([
            ("base_currency_id", "=", from_currency.id),
            ("target_currency_id", "=", to_currency.id),
            ("datetime", "<=", date_datetime),
        ], order="datetime DESC", limit=1)

        if exchange_rate:
            return exchange_rate.exchange_rate

        # Try reverse lookup
        reverse_rate = self.env["kojto.base.currency.exchange"].search([
            ("base_currency_id", "=", to_currency.id),
            ("target_currency_id", "=", from_currency.id),
            ("datetime", "<=", date_datetime),
        ], order="datetime DESC", limit=1)

        if reverse_rate and reverse_rate.exchange_rate != 0:
            calculated_rate = 1 / reverse_rate.exchange_rate
            return calculated_rate

        # If no rate found for the specific date, try to find the most recent rate available
        # Try most recent direct rate
        recent_rate = self.env["kojto.base.currency.exchange"].search([
            ("base_currency_id", "=", from_currency.id),
            ("target_currency_id", "=", to_currency.id),
        ], order="datetime DESC", limit=1)

        if recent_rate:
            return recent_rate.exchange_rate

        # Try most recent reverse rate
        recent_reverse = self.env["kojto.base.currency.exchange"].search([
            ("base_currency_id", "=", to_currency.id),
            ("target_currency_id", "=", from_currency.id),
        ], order="datetime DESC", limit=1)

        if recent_reverse and recent_reverse.exchange_rate != 0:
            calculated_rate = 1 / recent_reverse.exchange_rate
            return calculated_rate

        # If no exchange rate found, return 1.0 as fallback
        return 1.0

    def get_employee_name_for_printing(self):
        """Get employee name based on the trip's language"""
        self.ensure_one()
        if self.employee_id and self.language_id:
            # First try to find a name in the trip's language
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

    def get_company_name_for_printing(self):
        """Get company name based on the trip's language"""
        self.ensure_one()
        if self.company_id and self.language_id:
            # First try to find a name in the trip's language
            name_record = self.env['kojto.base.names'].search([
                ('contact_id', '=', self.company_id.id),
                ('language_id', '=', self.language_id.id),
                ('active', '=', True)
            ], limit=1)

            if name_record:
                return name_record.name
            else:
                # Fallback to the selected company name or company's default name
                return self.company_name_id.name if self.company_name_id else (self.company_id.name if self.company_id else "")
        elif self.company_name_id:
            # If no language specified, use selected name
            return self.company_name_id.name
        elif self.company_id:
            # Fallback to company's default name
            return self.company_id.name
        else:
            return ""

    def get_company_address_for_printing(self):
        """Get company address based on the trip's language"""
        self.ensure_one()
        if self.company_id and self.language_id:
            # First try to find an address in the trip's language
            address_record = self.env['kojto.base.addresses'].search([
                ('contact_id', '=', self.company_id.id),
                ('language_id', '=', self.language_id.id),
                ('active', '=', True)
            ], limit=1)

            if address_record:
                return address_record.name
            else:
                # Fallback to the selected company address
                return self.company_address_id.name if self.company_address_id else ""
        elif self.company_address_id:
            # If no language specified, use selected address
            return self.company_address_id.name
        else:
            return ""

    def get_employee_position_for_printing(self):
        """Return the employee position from the contract that matches the business trip date.

        Priority: contract covering date_start; if none, latest contract before date_start;
        fallback: employee's current position field if available; otherwise empty string.
        """
        self.ensure_one()
        if not self.employee_id or not self.date_start:
            return ""

        Contracts = self.env["kojto.hr.employees.contracts"]
        trip_start = self.date_start

        # 1) Contract covering the start moment
        covering_contract = Contracts.search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", "<=", trip_start),
            "|",
            ("date_end", ">=", trip_start),
            ("date_end", "=", False),
        ], order="date_start desc", limit=1)
        if covering_contract and covering_contract.position:
            return covering_contract.position

        # 2) Latest contract before start
        previous_contract = Contracts.search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", "<=", trip_start),
        ], order="date_start desc", limit=1)
        if previous_contract and previous_contract.position:
            return previous_contract.position

        # 3) Fallback to employee field if exists
        if "position" in self.employee_id._fields and self.employee_id.position:
            return self.employee_id.position

        return ""

