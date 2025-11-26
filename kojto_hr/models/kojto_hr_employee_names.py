"""
Kojto Employee Names Model

Purpose:
--------
Extends the base names model to include employee relationships,
allowing employees to have multiple names in different languages.
"""

from odoo import models, fields


class KojtoEmployeeNames(models.Model):
    _inherit = "kojto.base.names"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
