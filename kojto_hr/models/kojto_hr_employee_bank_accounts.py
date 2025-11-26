"""
Kojto Employee Bank Accounts Model

Purpose:
--------
Extends the base bank accounts model to include employee relationships,
allowing employees to have multiple bank accounts.
"""

from odoo import models, fields


class KojtoEmployeeBankAccounts(models.Model):
    _inherit = "kojto.base.bank.accounts"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
