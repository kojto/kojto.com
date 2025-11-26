# kojto_warehouses/models/kojto_warehouses_profile_shapes.py
from odoo import models, fields

class KojtoWarehousesProfileShapes(models.Model):
    _name = "kojto.warehouses.profile.shapes"
    _description = "Profile Shapes"
    _rec_name = "name"
    _order = "name asc"

    name = fields.Char("Name", size=450)
    standard = fields.Char(string="Standard", size=450)
    cross_section = fields.Float(string="Cross Section (mm2)")
    surface = fields.Float(string="Surface (m2/m)")
    active = fields.Boolean(string="Is Active", default=True)
