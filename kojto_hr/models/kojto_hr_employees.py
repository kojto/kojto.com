"""
Kojto HR Employees Model

Purpose:
--------
Core employee management model that handles employee information,
relationships, and user account creation.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class KojtoHrEmployees(models.Model):
    _name = "kojto.hr.employees"
    _description = "Kojto Hr Employees"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    name_2 = fields.Char(string="Name 2")
    active = fields.Boolean(string="Activity", default=True)

    employee_number = fields.Char(string="Employee Number", readonly=True, default=lambda self: self.get_next_employee_number())
    employee_images = fields.One2many("kojto.base.images", "employee_id", string="Employee Images")
    work_hours_terminal_binding = fields.Integer(string="Terminal Binding")
    position = fields.Char(string="Position")

    names = fields.One2many("kojto.base.names", "employee_id", string="Names")
    addresses = fields.One2many("kojto.base.addresses", "employee_id", string="Addresses")
    emails = fields.One2many("kojto.base.emails", "employee_id", string="Emails")
    phones = fields.One2many("kojto.base.phones", "employee_id", string="Phones")
    bank_accounts = fields.One2many("kojto.base.bank.accounts", "employee_id", string="Bank accounts")

    user_id = fields.Many2one("res.users", string="User", ondelete="set null")
    user_id_accountant = fields.Char(string="Accountant User ID")
    contracts = fields.One2many("kojto.hr.employees.contracts", "employee_id", string="Contracts")
    subcode_rates = fields.One2many("kojto.hr.employee.subcode.rates", "employee_id", string="Subcode Rates")

    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.hr.employees'), ('res_id', '=', id)]")

    can_see_attachments = fields.Boolean(compute="_compute_can_see_attachments", store=False)
    can_see_description = fields.Boolean(compute="_compute_can_see_description", store=False)

    @api.depends('user_id')
    def _compute_can_see_attachments(self):
        for rec in self:
            rec.can_see_attachments = (
                self.env.user.has_group('kojto_base.kojto_administrator')
                or self.env.user.has_group('base.group_erp_manager')
                or rec.user_id.id == self.env.user.id
            )

    @api.depends('user_id')
    def _compute_can_see_description(self):
        for rec in self:
            rec.can_see_description = (
                self.env.user.has_group('kojto_base.kojto_administrator')
                or self.env.user.has_group('base.group_erp_manager')
                or rec.user_id.id == self.env.user.id
            )

    @api.model
    def create(self, vals):
        employee = super(KojtoHrEmployees, self).create(vals)
        kojto_res_user_vals = {
            "name": employee.name,
            "login": employee.employee_number,
            "password": "default",
        }
        try:
            kojto_res_user_record = self.env["res.users"].create(kojto_res_user_vals)
            employee.user_id = kojto_res_user_record.id
        except Exception as e:
            raise ValidationError(_("Failed to create user: %s", str(e)))

        if "name" in vals and vals["name"]:
            self.env["kojto.base.names"].create({"name": vals["name"], "employee_id": employee.id, "active": True})

        # Automatically create default subcode rate
        last_used_subcode_rate = self.env["kojto.hr.employee.subcode.rates"].search([], order="create_date desc, id desc", limit=1)
        if last_used_subcode_rate and last_used_subcode_rate.subcode_id:
            default_subcode = last_used_subcode_rate.subcode_id
        else:
            default_subcode = self.env["kojto.commission.subcodes"].search([], limit=1)
        if default_subcode:
            self.env["kojto.hr.employee.subcode.rates"].create({
                "employee_id": employee.id,
                "subcode_id": default_subcode.id,
                "datetime_start": fields.Datetime.now(),
                "hour_rate": 1,
            })

        return employee

    def write(self, vals):
        result = super(KojtoHrEmployees, self).write(vals)

        if "name" in vals and vals["name"]:
            for record in self:
                name_record = self.env["kojto.base.names"].search([("employee_id", "=", record.id)], limit=1)
                if name_record:
                    name_record.update({"name": vals["name"]})
                else:
                    self.env["kojto.base.names"].create({"name": vals["name"], "employee_id": record.id, "active": True})

        return result

    def get_next_employee_number(self):
        last_employee = self.search([], order="employee_number desc", limit=1)

        if not last_employee:
            return "E00001"

        last_employee_number = last_employee.employee_number
        numeric_part = int(last_employee_number[1:])
        new_numeric_part = numeric_part + 1

        return "E" + str(new_numeric_part).zfill(5)

    @api.constrains("user_id")
    def check_unique_user_id(self):
        for employee in self:
            if employee.user_id:
                existing_employee = self.env["kojto.hr.employees"].search([("user_id", "=", employee.user_id.id), ("id", "!=", employee.id)], limit=1)
                if existing_employee:
                    raise ValidationError("A user can only be associated with one employee. " "User (ID: %s) is already associated with employee (ID: %s)." % (employee.user_id.name, existing_employee.name))
