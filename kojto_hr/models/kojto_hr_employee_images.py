"""
Kojto Employee Images Model

Purpose:
--------
Extends the base images model to include employee relationships,
allowing employees to have multiple images.
"""

from odoo import models, fields


class KojtoBaseImagesInherited(models.Model):
    _inherit = "kojto.base.images"

    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", ondelete="set null")
