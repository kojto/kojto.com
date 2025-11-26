"""
Kojto HR Employee Contracts Model

Purpose:
--------
Manages employee contracts, including position, work duration,
contract dates, and contract documents.
"""
from odoo import models, fields, api


class KojtoHrEmployeesContracts(models.Model):
    _name = "kojto.hr.employees.contracts"
    _description = "Kojto Hr Employees Contracts"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
    position = fields.Char(string="Position", translate=True)
    description = fields.Char(string="Description")
    work_day_duration = fields.Float(string="Worktime")
    date_start = fields.Date(string="From", required=True)
    date_end = fields.Date(string="To")
    contract = fields.Binary(string="Contract")
    number_contract = fields.Char(
        string="Number",
        compute="compute_number_contract",
        store=True,
        readonly=False,
        inverse="_inverse_number_contract")

    can_see_contracts = fields.Boolean(compute="_can_see_contracts", store=False)

    @api.depends("employee_id")
    def compute_number_contract(self):
        for record in self:
            count = len(
                self.search(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("id", "!=", record.id),
                        ("date_start", "<", record.date_start),
                    ]
                )
            )
            number = "TD_" + str(record.employee_id.employee_number) + "_" + str(count)
            record.number_contract = number


    @api.depends('employee_id.user_id')
    def _can_see_contracts(self):
        for rec in self:
            rec.can_see_contracts = (
                self.env.user.has_group('kojto_base.kojto_administrator')
                or self.env.user.has_group('base.group_erp_manager')
                or (rec.employee_id and rec.employee_id.user_id.id == self.env.user.id)
            )

    def _inverse_number_contract(self):
        # This method can be empty if you just want to allow manual editing.
        # If you want to do something special when the user edits, add logic here.
        pass


