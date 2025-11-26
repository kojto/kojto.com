"""
Kojto Employee Addresses Model

Purpose:
--------
Extends the base addresses model to include employee relationships,
allowing employees to have multiple addresses.
"""

from odoo import models, fields


class KojtoEmployeeAddresses(models.Model):
    _inherit = "kojto.base.addresses"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
