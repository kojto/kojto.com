"""
Kojto HR Employee Subcode Rates Dashboard Model

Purpose:
--------
Dashboard view that shows active employees with their latest subcode rates,
including subcode, currency, and hour rate information.
"""

from odoo import models, fields, api, tools


class KojtoHrEmployeeSubcodeRatesDashboard(models.Model):
    _name = "kojto.hr.employee.subcode.rates.dashboard"
    _description = "Kojto HR Employee Subcode Rates Dashboard"
    _auto = False  # This is a database view

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", readonly=True)
    employee_name = fields.Char(string="Employee Name", readonly=True)
    employee_number = fields.Char(string="Employee Number", readonly=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", readonly=True)
    subcode_name = fields.Char(string="Subcode Name", readonly=True)
    date_start = fields.Date(string="Valid From", readonly=True)
    hour_rate = fields.Float(string="Hour Rate", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    currency_symbol = fields.Char(string="Currency Symbol", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT DISTINCT ON (e.id, esr.subcode_id)
                    esr.id,
                    e.id as employee_id,
                    e.name as employee_name,
                    e.employee_number,
                    esr.subcode_id,
                    sc.name as subcode_name,
                    esr.date_start,
                    esr.hour_rate,
                    esr.currency_id,
                    c.symbol as currency_symbol
                FROM kojto_hr_employees e
                INNER JOIN kojto_hr_employee_subcode_rates esr ON e.id = esr.employee_id
                INNER JOIN kojto_commission_subcodes sc ON esr.subcode_id = sc.id
                INNER JOIN res_currency c ON esr.currency_id = c.id
                WHERE e.active = true
                ORDER BY e.id, esr.subcode_id, esr.date_start DESC
            )
        """ % self._table)
