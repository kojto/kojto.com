from odoo import models, fields

class KojtoProfileConfiguratorLibrary(models.Model):
    _name = "kojto.profile.configurator.library"
    _description = "Kojto Profile Configurator Library"
    _rec_name = "name"

    name = fields.Char(string="Standard Profile Name")
    material_id = fields.Many2one("kojto.base.material.grades")
    a1 = fields.Float()
    a2 = fields.Float()
    b1 = fields.Float()
    b2 = fields.Float()
    b3 = fields.Float()
    c1 = fields.Float()
    c2 = fields.Float()
    c3 = fields.Float()
    d1 = fields.Float()
    d3 = fields.Float()
