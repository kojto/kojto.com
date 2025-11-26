"""
Kojto Employee Phones Model

Purpose:
--------
Extends the base phones model to include employee relationships,
allowing employees to have multiple phone numbers.
"""

from odoo import models, fields


class KojtoEmployeePhones(models.Model):
    _inherit = "kojto.base.phones"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
