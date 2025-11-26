"""
Kojto Employee Emails Model

Purpose:
--------
Extends the base emails model to include employee relationships,
allowing employees to have multiple email addresses.
"""

from odoo import models, fields


class KojtoEmployeeEmails(models.Model):
    _inherit = "kojto.base.emails"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
